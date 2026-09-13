---
name: run
description: Launch, test, and troubleshoot the Lean 4 Autoformalizer app (FastAPI backend + Vite/React frontend + real Lean toolchain) for local development.
---

# Running the Lean 4 Autoformalizer locally

This is the verified path for this repo specifically -- use it instead of
rediscovering setup from scratch. It's `deploy/local-deploy.sh` plus the
gotchas that aren't obvious from a cold start.

## Prerequisites

- **Python 3.12+**
- **Node.js >= 20.19.0 or >= 22.12.0.** Vite 8's rolldown bundler ships a
  native binary as a platform-specific optional dependency gated on that
  exact engine range. An older Node (e.g. 20.18.x) doesn't error on
  `npm install` -- it silently skips installing the binary, and the failure
  only shows up later as a confusing `Cannot find module
  '@rolldown/binding-linux-x64-gnu'` at build/dev time. Check with
  `node --version`; manage it with `nvm` if it's a loose/manually-placed
  binary rather than a real package-manager install.
- **Lean 4 toolchain via elan** (`~/.elan/bin/lean`, `~/.elan/bin/lake`).
  Without it, the backend still runs and falls back to a heuristic mock
  Lean validator (`ALLOW_MOCK_FALLBACK=true` in `.env`).
- **Optional: a Mathlib-linked Lake project** for real Lean verification
  with `Mathlib.*` imports -- set `LEAN_PROJECT_DIR` in `backend/.env` to
  its path. Without it, bare `lean` runs with no extra library search path
  (fine for basic `Nat`/`Int` proofs, not for anything needing Mathlib).
- **Optional: a Gemini API key** (`GEMINI_API_KEY` in `backend/.env`) for
  real LLM formalization. Without one, `/api/formalize` falls back to a
  regexp-based mock formalizer -- still returns valid Lean code for simple
  algebraic statements, just not general natural-language reasoning.

## Start / stop / status

```bash
deploy/local-deploy.sh start
deploy/local-deploy.sh status
deploy/local-deploy.sh stop
```

- Binds both servers to `0.0.0.0`, so if Tailscale is running it prints a
  Tailscale URL too -- useful for testing from a phone.
- **Always stop it with `local-deploy.sh stop`, not a raw `pkill` on the
  uvicorn process.** Killing the backend while a Lean subprocess is mid-check
  used to orphan that subprocess -- Lean has no self-timeout, so an orphan
  just runs forever, burning CPU/memory until someone notices and kills it
  by hand (this actually happened: a single stuck `lean` process ran for
  over an hour, using 1.4GB RAM). There's now a shutdown hook that cleans
  these up on a graceful stop, but `local-deploy.sh stop` is still the
  path that exercises it.
- If you ever suspect a runaway Lean process regardless: `ps aux --sort=-%mem | grep lean` and check `ELAPSED` time with `ps -p <pid> -o etime`. A `lean`/`lake` process running longer than `LEAN_TIMEOUT_SECS` (default 60s, in `backend/.env`) is a bug, not normal.

## Testing the backend without touching the frontend

FastAPI auto-generates an interactive API explorer -- **no frontend
changes or curl syntax needed**:

```
http://localhost:8000/docs
```

Expand an endpoint (`/api/formalize`, `/api/prove`, `/api/verify`), "Try it
out", edit the JSON body, "Execute". This is the fastest way to test a
backend-only change.

Quick health check: `curl http://localhost:8000/api/status` -- reports
`lean_installed`, `gemini_key_configured`, and the active `model`.

## Running the test suites

```bash
cd backend && source .venv/bin/activate && PYTHONPATH=. pytest -v
cd frontend && npx tsc --noEmit && npm run build
```

## Known gotchas

- **First Lean call after a (re)start is slow.** Cold `lake env` startup can
  take several seconds to over a minute the first time. `lean_installed:
  false` on the very first `/api/status` call right after starting is often
  just this cold start racing a 5s internal check timeout, not a real
  failure -- it resolves on the next call.
- **Gemini model names get deprecated by Google without warning.** If
  `/api/formalize` starts returning `source: "mock"` with a `404 ... no
  longer available to new users` error, the configured model has been
  retired. Verify directly against the live API before changing anything
  (don't guess from training data -- model availability changes faster than
  any model's knowledge cutoff):
  ```python
  from google import genai
  client = genai.Client(api_key="...")
  client.models.generate_content(model="gemini-3.6-flash", contents="hi")
  ```
  Then update `GEMINI_MODEL` in `backend/app/config.py` / `.env.example`
  and the dropdown in `frontend/src/components/SettingsModal.tsx`.
- **The frontend caches the chosen model/key in browser `localStorage`**
  (`GEMINI_MODEL`, `GEMINI_API_KEY`). Changing the server-side default
  doesn't override a value a browser already saved via the Settings modal --
  it has to be re-picked there too.
- **`/api/formalize` always returns a `:= by sorry` stub by default.**
  Proving is a separate step (`/api/prove`, or pass `auto_prove: true` in
  the formalize request to also run the free deterministic tactics --
  `omega`/`rfl`/`simp`/`aesop` -- inline, no extra LLM cost).
- **429/503 from Gemini are retried automatically** (`GEMINI_MAX_RETRIES`
  in `.env`, default 1 = no retry), except a 429 caused by an exhausted
  *daily* quota, which fails immediately rather than burning more of a
  scarce quota on calls guaranteed to fail again for hours.

## Headless browser testing (agent/CI context)

If driving the UI with Playwright in a container/sandbox with no display
and no root, Chromium needs a few shared libraries
(`libnspr4`, `libnss3`, `libasound2`) that may not be preinstalled and
can't be `apt-get install`ed without sudo. Work around it without root by
downloading the `.deb`s (`apt-get download` doesn't need root, it just
fetches) and extracting them locally:

```bash
mkdir -p /tmp/pwdeps/extracted && cd /tmp/pwdeps
apt-get download libnspr4 libnss3 libasound2
for f in *.deb; do dpkg-deb -x "$f" extracted/; done
export LD_LIBRARY_PATH="/tmp/pwdeps/extracted/usr/lib/x86_64-linux-gnu:$LD_LIBRARY_PATH"
npx playwright install chromium   # if not already downloaded
```
If you have root, just `sudo apt-get install -y libnspr4 libnss3 libasound2`
instead -- permanent, no per-session workaround needed.
