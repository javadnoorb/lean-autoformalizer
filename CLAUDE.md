# CLAUDE.md

Lean 4 autoformalizer + prover: FastAPI backend (`backend/`) that shells out
to a real Lean toolchain and calls Gemini, and a Vite/React/Monaco frontend
(`frontend/`). For launching, debugging, and environment gotchas, use the
`run` skill (`.claude/skills/run/SKILL.md`) rather than rediscovering setup.

## Commands

```bash
cd backend && PYTHONPATH=. pytest -q          # backend tests (what CI runs)
cd frontend && npm run build                  # tsc type-check + vite build (what CI runs)
deploy/local-deploy.sh start|status|stop      # run both servers locally
```

CI (`.github/workflows/`) only runs the backend job when `backend/**`
changes and the frontend job when `frontend/**` changes. There is no
frontend test suite or linter beyond `tsc`.

## Backend layout

- `app/main.py` -- all routes; maps service exceptions to HTTP status codes.
  The `lifespan` shutdown hook kills in-flight Lean processes.
- `app/config.py` -- every setting, each overridable by env var / `backend/.env`.
- `app/models/schemas.py` -- all request/response Pydantic models.
- `app/services/` -- one module per concern, each exposing a module-level
  singleton (`lean_runner`, `autoformalizer`, `prover`, `leandojo_harness`).
- `app/prompts/` -- LLM prompt templates.
- `tests/` -- pytest with FastAPI `TestClient`. Tests must pass with no
  Gemini key and no Lean toolchain installed (CI has neither).

A new feature normally touches config -> schemas -> service -> route ->
tests in that order.

## Conventions

- **Degrade, don't crash.** Missing Lean, Gemini key, or optional packages
  fall back to mock behavior (`ALLOW_MOCK_FALLBACK`) and responses say so
  (`source: "mock"` + `source_detail`). Heavy optional dependencies
  (`lean_dojo`, PyPantograph) are *not* in `requirements.txt`; import them
  lazily and report `available: false` from a status method, following
  `leandojo_harness.py`.
- **Never leak Lean processes.** Lean has no self-timeout, so any
  subprocess or long-lived Lean server must be tracked and killed on
  timeout and on app shutdown (see `lean_runner.kill_all_active()`).
- **Cost-aware defaults.** Anything that spends money (Gemini calls,
  retries, cloud VMs) defaults to the cheapest behavior and is opt-in to
  raise -- e.g. `GEMINI_MAX_RETRIES=1`, throwaway VMs auto-destroy.
- **Test external dependencies with fakes**, not network or toolchain
  calls; keep real end-to-end checks in `deploy/` scripts instead.
- **Don't trust model/tool versions from memory.** Gemini model names get
  retired; Lean/Mathlib APIs change. Verify against the live API or
  installed source before changing them.
- Comments explain *why* (the failure mode being prevented), not what.

## Pull requests

The owner reviews everything, so keep PRs small and single-purpose:
separate docs, deploy/infra scripts, behavior-preserving refactors, and
feature code into their own PRs, and stack them (base each on the previous
branch) when they depend on each other. Put the test plan in the PR body,
including anything not yet verified against a real Lean/Mathlib install.
