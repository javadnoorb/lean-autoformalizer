---
name: lean-interactive-search
description: Findings from investigating deep interactive Lean tactic search (incremental tactic-state interaction, tree search, eventual DeepSeek-Prover integration) for this app. Read this BEFORE attempting LeanDojo, building a persistent-Lean-process wrapper, or evaluating LeanCopilot/PyPantograph -- it records what was already tried, what failed and why, and what's still unverified, so that work isn't repeated from scratch.
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

**Found two more actively-maintained, purpose-built candidates, neither yet
tested against this project -- evaluate these before hand-rolling a `repl`
wrapper:**

- **[LeanCopilot](https://github.com/lean-dojo/LeanCopilot)** (from the same
  org as LeanDojo, but far more actively maintained -- commits weeks old at
  time of writing, pinned to `leanprover/lean4:v4.33.0`, essentially this
  project's exact version). Ships as a *Lean package* providing native
  tactics (`suggest_tactics`, `search_proof`, `select_premises`) callable
  from inside a `.lean` proof. Bigger paradigm shift from this app's
  Python-orchestrates-everything architecture -- the model-calling
  mechanism lives inside Lean, not in `autoformalizer.py`/`prover.py`.
  Not yet checked how it calls out to an LLM (bundled local model vs.
  configurable external API) -- check this first if evaluating it.
- **[PyPantograph](https://github.com/stanford-centaur/PyPantograph)**
  (`stanford-centaur` org; paper: arXiv:2410.16429). Python-side
  machine-to-machine interaction library -- `pip`/`uv`-installable,
  provides `goal_tactic` (incremental tactic application, the actual
  primitive needed here) and `check_track` (whole-file check, same shape as
  today's `lean_runner.py`). Ships MCTS search-state handling natively
  (recent commit: "Fix MCTS search state advancement"). No evidence in its
  README of a mandatory LeanDojo-style full-repo tracing step, but **this
  has not been empirically verified against this project** the way LeanDojo
  was -- don't assume it's friction-free until it's actually been run here.
  Given this app's architecture (Python/FastAPI orchestrating an LLM), this
  is the more natural fit of the two to evaluate first.

## Recommended next step

Do **not** re-attempt LeanDojo. Before hand-building a `repl`-JSON-protocol
wrapper from scratch, spend a small, time-boxed session actually installing
and testing **PyPantograph** against this project (or the Mathlib-free
`dojo_toy` project first, for a cheap initial check) -- confirm whether it
avoids LeanDojo's tracing tax, and whether `goal_tactic` gives the
incremental interaction this app needs. Only fall back to raw `repl` +
hand-rolled JSON plumbing if PyPantograph turns out not to fit.
