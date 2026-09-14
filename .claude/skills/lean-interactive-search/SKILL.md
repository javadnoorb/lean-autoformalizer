---
name: lean-interactive-search
description: Findings from investigating deep interactive Lean tactic search (incremental tactic-state interaction, tree search, eventual DeepSeek-Prover integration) for this app. Read this BEFORE attempting LeanDojo, PyPantograph's Mathlib path, building a persistent-Lean-process/repl wrapper, or evaluating LeanCopilot -- it records what was already tried, what failed and why (both LeanDojo and PyPantograph hit the same Mathlib-import resource tax), and what's still unverified, so that work isn't repeated from scratch.
---

# Deep interactive Lean search: investigation findings

## The goal

The current app (`lean_runner.py`, `prover.py`) does one-shot verification: write a
whole Lean file, spawn `lean`/`lake env lean` as a fresh subprocess, parse the
JSON diagnostics. The fast-hammer prover works by substring-replacing `sorry`
with a candidate tactic and re-running the *entire file* through a fresh
process for every single tactic attempt.

The eventual goal is deeper, incremental interactive search: apply one
tactic, get the resulting goal state back, try another, backtrack -- without
re-elaborating the whole file (and re-importing Mathlib) on every attempt --
ideally driven by a specialized model like DeepSeek-Prover. This doc is about
finding the right foundation for that, not implementing it yet.

## What was tried: LeanDojo -- don't readopt without rereading this section

**Verdict: do not use LeanDojo as currently released (`lean-dojo` 4.20.0, PyPI,
last released June 2025). It is meaningfully behind current Lean and the
integration cost is disproportionate to the benefit.**

Concretely, on this project (`add_sq_demo`, Lean `v4.33.1`, full Mathlib
dependency):

1. **Local-repo caching is expensive by itself.** `LeanGitRepo` for a local
   path copies the *entire* working directory -- including the already-built
   `.lake/build` output -- into `~/.cache/lean_dojo/repos/` before doing
   anything else. For a Mathlib-dependent project this alone moved **7.4GB
   across 139,156 files** and didn't finish in 15 minutes. This is not
   Mathlib-specific: even a trivial, Mathlib-free toy project still copies
   Lean 4's own toolchain/stdlib build output (~2.7GB) the same way, since
   LeanDojo treats the Lean4 repo itself as a lake dependency to be cached.
2. **After caching, `trace()` failed to even compile**, with real errors in
   LeanDojo's *own* bundled instrumentation script
   (`lean_dojo/data_extraction/ExtractData.lean`), not the target project:
   - `String.Pos`/`Substring` were redesigned in current Lean into
     dependently-indexed types, with `.Raw` as the plain non-indexed escape
     hatch (`String.Pos.Raw`, `Substring.Raw`). Fix: change the two `ToJson`
     instances and the `TacticTrace.pos`/`endPos` field types from
     `String.Pos`/`Substring` to `.Raw`, and use `.byteIdx` /
     `Substring.Raw.toString` accordingly. (`Syntax.getPos?`/`getTailPos?`
     already return `.Raw` natively in current Lean, so call sites that
     *use* those didn't need changes -- only the type declarations did.)
   - `String.drop`/`String.trim` now return a new `String.Slice` type
     instead of `String`. `.trim` has a still-working deprecated shim (just a
     warning); `.drop` does not (hard error). Fix: append `.toString` at the
     two `.drop` call sites (lines defining `defPath`).
   - **Both fixes were verified directly** by compiling small standalone
     snippets against the real installed toolchain before editing the real
     file (see the pattern: write a `#check`/`#eval` snippet, run
     `lake env lean <snippet>`, only then apply the fix) -- this is much
     faster than guessing and re-running the full (multi-minute) trace after
     each guess.
   - After both fixes, tracing a **Mathlib-free toy project**
     (`/home/javad/projects/lean-test/dojo_toy`, git-committed, no Mathlib
     dependency) genuinely progressed past both errors into real elaboration
     -- confirmed via `2486` total items to trace and real `lean --run
     ExtractData.lean <file>` worker processes actively consuming CPU/RAM,
     not stalled.
3. **Even fixed, the timeline is bad.** Tracing that trivial toy project's
   2,486 items (almost entirely Lean's own `Init`/`Std` library, not our one
   theorem) was still running at a stabilized rate implying **2-4+ hours**
   to finish, because LeanDojo traces the *entire* dependency graph
   (including Lean's own stdlib) before you can interact with anything.
4. **There's at least one more known, unrelated, unfixed break** further
   down the pipeline: an open GitHub issue
   ([lean-dojo/LeanDojo#252](https://github.com/lean-dojo/LeanDojo/issues/252),
   filed Dec 2025, zero maintainer replies as of this writing) describes
   `Lean4Repl.lean` (needed for the actual `Dojo.run_tac` interaction phase,
   which we never reached) failing on `NameSet.union` after Lean's `NameSet`
   backing structure changed. This wasn't fixed or verified here -- tracing
   never got far enough to hit it. The pattern (LeanDojo hard-codes Lean
   internals that keep moving) means there could be more beyond this one.
5. **Operational hazard, independent of the above**: killing a LeanDojo
   trace process tree is not as simple as killing the top-level PID --
   LeanDojo spawns real `lean --run ExtractData.lean <file>` worker
   processes (multi-GB RSS each) that are *not* direct children of the
   Python process that started `trace()`. A naive `pkill -P <pid>` during
   cleanup left two such workers running (2.7GB and 2.0GB RSS) after the
   "kill" completed. If ever running LeanDojo again, track and kill by
   matching the process command (`pkill -f ExtractData.lean`) or a process
   group, not just `-P <parent_pid>`.

The local venv copy of `ExtractData.lean` at
`backend/.venv/lib/python3.12/site-packages/lean_dojo/data_extraction/ExtractData.lean`
has both fixes applied, but **this is a local, uncommitted patch to a
third-party package inside a gitignored `.venv/` -- it will not survive a
fresh `pip install` and is not part of this repo's source.** If picking
LeanDojo back up, reapply from this doc rather than assuming the patch
persists anywhere.

Scratch test artifacts from this investigation (not part of the app, local
only): `/home/javad/projects/lean-test/dojo_toy` (a committed, Mathlib-free
toy Lean project built specifically to test LeanDojo cheaply) and a first
commit added to the previously-uncommitted `/home/javad/projects/lean-test/add_sq_demo`
(needed because `LeanGitRepo` requires a commit hash).

## Is this reinventing the wheel? What already exists

**DeepSeek-Prover itself does not use LeanDojo at runtime.** Checked directly
against `deepseek-ai/DeepSeek-Prover-V1.5`'s actual published code (not just
the paper): `lean_dojo` appears nowhere in `requirements.txt` or anywhere in
`prover/lean/`. What they actually do:

- Call `lake exe repl` (the community tool `leanprover-community/repl`)
  directly via plain `subprocess.run`, feeding it one JSON command
  (`{"cmd": <code>, "env": <prior_env_id>, ...}`) over stdin per call, and
  parsing JSON back (`errors`/`sorries`/`tactics`/`env`). This is
  structurally very close to this app's own `lean_runner.py` -- spawn a
  process, feed code, parse JSON -- just using `repl` instead of bare
  `lean --json <file>` for richer, tactic-level output.
- Their non-interactive verifier (`prover/lean/verifier.py`) runs a pool of
  independent OS processes doing one-shot whole-proof verification --
  essentially what this app's `lean_runner.py`/fast-hammer loop already does,
  just parallelized across a worker pool.
- `repl`'s actual incrementality trick is **pickling**: bake a fully
  Mathlib-imported environment to an `.olean` snapshot file *once*
  (`{"pickleTo": "path", "env": N}`), then any later `repl` process can
  `unpickleEnvFrom` that file and resume in milliseconds instead of
  re-importing Mathlib from source. This is a fundamentally lighter
  mechanism than LeanDojo's static whole-repo tracing/instrumentation.
- `repl` is actively maintained *by the Lean community itself*, not a
  separate research project -- pinned toolchain was `v4.34.0-rc2` at time of
  writing (one minor version ahead of this project's `v4.33.1`), with
  toolchain-bump commits roughly matching every Lean release/RC. Far lower
  version-drift risk than LeanDojo.
- DeepSeek-Prover-V2 (Apr 2025, 671B MoE + 7B variants) is open-weight and
  available via third-party hosted APIs (Fireworks AI, Poe) -- but this gets
  you *a model*, not a packaged search/interaction product. The interactive
  search loop around it is still something you (or DeepSeek's own,
  not-fully-open-sourced tree-search code) has to build. Confirms: adopting
  DeepSeek-Prover later means "call this model via API instead of Gemini,
  feed it into our own search loop" -- not "install DeepSeek's finished
  product."

**Found two more actively-maintained, purpose-built candidates:**

- **[LeanCopilot](https://github.com/lean-dojo/LeanCopilot)** (from the same
  org as LeanDojo, but far more actively maintained -- commits weeks old at
  time of writing, pinned to `leanprover/lean4:v4.33.0`, essentially this
  project's exact version). Ships as a *Lean package* providing native
  tactics (`suggest_tactics`, `search_proof`, `select_premises`) callable
  from inside a `.lean` proof. Bigger paradigm shift from this app's
  Python-orchestrates-everything architecture -- the model-calling
  mechanism lives inside Lean, not in `autoformalizer.py`/`prover.py`.
  Not yet checked how it calls out to an LLM (bundled local model vs.
  configurable external API), and not yet empirically tested here.
- **[PyPantograph](https://github.com/stanford-centaur/PyPantograph)** --
  tested against this project (see below). **Verdict: excellent for
  Mathlib-free interaction, but hits the same resource tax as LeanDojo the
  moment Mathlib enters the picture. Do not re-attempt the Mathlib path
  without a real fix (see below) -- it will burn 30+ minutes of pegged CPU
  and multi-GB RAM per attempt and still not finish.**

### PyPantograph: tested, mixed result

`pip install`-able (package name `pantograph` on PyPI, `0.3.15`). Bundles a
self-contained `pantograph-repl` binary (~247MB) plus a `lean-toolchain`
file baked in at build time from a git submodule
(`src/` -> `leanprover/Pantograph`, the official Lean org's fork, not a
research side-project).

**Gotcha found and fixed**: PyPantograph's `main` branch on PyPI/GitHub had
its `src/` submodule pinned to a `leanprover/Pantograph` commit from
`v4.29.1` (stale -- last bumped on PyPantograph's side well before Lean's
own repo advanced). Symptom: `Server(imports=['Mathlib'], project_path=...)`
against this project (`v4.33.1`) fails immediately with `uncaught exception:
failed to read file '.../Mathlib.olean', incompatible header`. Checked
PyPantograph's own PR #176 (`build/version` branch) -- an official,
unmerged, but insufficient bump to only `v4.30.0`. **Fix**: clone fresh with
`--recurse-submodules`, then manually re-point the submodule to match your
project's exact toolchain and rebuild:
```bash
git clone --recurse-submodules https://github.com/stanford-centaur/PyPantograph.git /tmp/PyPantograph
cd /tmp/PyPantograph/src && git fetch origin dev && git checkout <commit-matching-your-lean-toolchain>
cd /home/javad/projects/lean-autoformalizer/backend && source .venv/bin/activate
pip uninstall -y pantograph && pip install /tmp/PyPantograph
```
Verify with `cat .venv/lib/python3.12/site-packages/pantograph/lean-toolchain`
-- must exactly match your project's `lean-toolchain`. (We used commit
`92d4818a4b343d7be293731e03359a19e8082626`, "Merge pull request 'build:
Update Lean to v4.33.1, version to 0.3.19' (#347)", to match this project's
`v4.33.1`.)

**With versions matched, `Init`-only interaction works great** --
`Server(imports=['Init'])`, `goal_start(statement)`,
`goal_tactic(state, tactic=..., site=Site(goal_id=...))` all behave exactly
as documented. Verified multi-step + branching + per-goal targeting +
completion detection end-to-end:
`forall (p q: Prop), Or p q -> Or q p` via `intro` -> `cases h` (produces
`case inl`/`case inr`) -> `Site(goal_id=0)` targeting -> `right; assumption`
/ `left; assumption` -> `state.is_solved == True`. This is genuinely the
incremental tactic-state primitive this app needs, and it's fast (seconds,
not minutes).

**But `imports=['Mathlib']` reproduces LeanDojo's resource tax, just via a
different mechanism.** Tested against `add_sq_demo` (Mathlib already fully
built in `.lake/build`, versions exactly matched, no `.olean` header
error this time): `Server(imports=['Mathlib'], project_path='.../add_sq_demo',
timeout=1800)` ran for **35+ minutes, pegged at ~84% CPU, ~1.2GB RSS, and
never emitted the "ready" signal** -- the constructor raised
`RuntimeError: Server failed to emit ready signal in time` after the
30-minute timeout, but the underlying `pantograph-repl` subprocess kept
running (CPU still pegged, RSS still fluctuating around 1.2GB) as an
**orphan** after the Python process exited, because the exception path in
`Server.__init__`/`restart_async` never calls `self._close()` on failure.
Confirmed via `/proc/<pid>/environ` that `LEAN_PATH` correctly pointed at
the prebuilt `.lake/build/lib/lean` dirs (including
`.../mathlib/.lake/build/lib/lean`) -- this is not a misconfiguration, the
process had access to the prebuilt `.olean` files and was still that slow.
**Same operational hazard as LeanDojo**: kill orphaned `pantograph-repl` by
matching the process name (`pkill -9 -f pantograph-repl`), not just the
parent PID -- `Server._close()`/`proc.terminate()` is never reached when
`restart_async` raises.

This means PyPantograph's `imports=['Mathlib']` startup is *not* free of
the tracing-style tax the LeanDojo section above describes -- it just pays
it as a one-time-per-process-startup import/elaboration cost instead of a
static whole-repo trace.

**Root-caused: this is machine resources, not a PyPantograph/LeanDojo
defect.** Isolated it by dropping both tools entirely and timing bare
`lake env lean` on a file containing only `import Mathlib` in this same
project: **1h08m wall clock**, with `/usr/bin/time -v` showing 292s user
time vs **3421s system time** and **599,255 major page faults** -- a
thrashing signature, not a compute-bound one. Root cause: this dev
machine's Mathlib build (`.lake/packages/mathlib/.lake/build/lib/lean`) is
**6.0GB** of compiled `.olean` data, and this machine's WSL2 VM is capped
at **6GB RAM** (`.wslconfig`: `memory=6GB`) because the physical host only
has **7.8GB total RAM** -- there's essentially no headroom to raise the
cap without starving Windows itself. Holding the *entire* Mathlib
environment resident in one process needs more memory than this box can
give it, so it constantly evicts and re-reads pages from disk. This isn't
fixable in software and isn't specific to PyPantograph -- LeanDojo's own
multi-hour tax (documented above) is almost certainly the same underlying
cause, just manifesting as static tracing instead of a live import. On a
machine with more RAM (the 8-16GB+ commonly recommended for Mathlib work),
both LeanDojo's trace step and PyPantograph's `imports=['Mathlib']` could
plausibly be fine -- **don't conclude either tool is broken from tests run
on this machine; re-test on better hardware before ruling either out.**

The app's existing prover never hit this wall because its LLM prompt
(`prompts/autoformalize.py`) explicitly avoids `import Mathlib` and sticks
to stdlib types unless Mathlib is specifically required -- i.e. it already
avoids the failure mode above by keeping each process's working set small,
which is worth keeping in mind as a mitigation for interactive search too
(scope imports to what's actually needed instead of the whole umbrella). **Checked for a `repl`-style pickling escape hatch -- there isn't one.**
Grepped the installed package (`server.py`, `utils.py`) and the
`pantograph-repl` binary itself (`--help` / bad-arg output) for anything
like `pickleTo`/`unpickleEnvFrom`. The only pickle-related code found is in
`test_server.py` (`goal-state.pickle`), which is plain Python `pickle` of a
`GoalState` object for test fixture reuse -- unrelated to caching a
Lean/Mathlib environment. The `pantograph-repl` binary takes only
import-name and option args (no snapshot/cache flag). **Confirmed: current
PyPantograph has no environment-caching mechanism.** Every `Server(imports=
['Mathlib'], ...)` call pays the full import cost from scratch.

## Recommended next step

Do **not** re-run PyPantograph's `imports=['Mathlib']` path (or LeanDojo's
trace step) on this same resource-constrained dev machine (6GB RAM cap)
expecting a different result -- it's a hardware ceiling, not a bug, and
will burn another 30+ minutes and orphan another multi-GB process every
time. Given the root cause is machine memory, not the tools, there are two
independent axes to pursue, and they're not mutually exclusive:

1. **Avoid needing the full Mathlib environment resident at once**, the
   same way this app's existing prover already does: scope imports to
   specific `Mathlib.X.Y` modules instead of the whole-umbrella
   `import Mathlib`, whichever interactive tool ends up used. Untested
   here so far, but plausible given the app's own working precedent.
   `leanprover-community/repl`'s pickling (bake a Mathlib-imported
   environment to disk once, `unpickleEnvFrom` it cheaply thereafter) is
   the other way to amortize this cost -- still the most promising
   concrete option if full-Mathlib access is actually required, and it's
   the same mechanism DeepSeek-Prover itself relies on.
2. **Re-test PyPantograph (and possibly LeanDojo) on a machine with more
   RAM** (8-16GB+ commonly recommended for Mathlib work) before ruling
   either out for real -- the negative results recorded above are only
   verified to be true *on this specific 6GB-capped box*.

Before committing to hand-rolling a `repl` wrapper (more work than
adopting a library), it's still worth a quick, time-boxed check of
LeanCopilot's LLM-calling mechanism (not yet looked at) in case it
sidesteps this problem in a different way.
