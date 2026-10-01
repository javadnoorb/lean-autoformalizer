#!/usr/bin/env bash
# Runs ON the throwaway benchmark VM (as root, no hardening -- see
# pantograph-service-bench.sh for why). Sets up the same version-matched
# PyPantograph install as pantograph-bench-remote.sh, then deploys this
# app's actual backend (at git ref $BENCH_REF) and exercises the real
# /api/interactive/* endpoints end-to-end against real Mathlib -- this can
# never be verified on the local dev machine (6GB RAM cap).
set -euo pipefail

PROJECT_DIR="$HOME/pantograph_test_project"
PANTOGRAPH_SRC="$HOME/PyPantograph"
REPO_DIR="$HOME/lean-autoformalizer"
BENCH_REF="${BENCH_REF:-main}"
# Commit of leanprover/Pantograph already verified locally to match Lean
# v4.33.1 exactly -- see .claude/skills/lean-interactive-search/SKILL.md.
PANTOGRAPH_SUBMODULE_REV="92d4818a4b343d7be293731e03359a19e8082626"

log() { echo "[$(date +%H:%M:%S)] $*"; }

log "Installing base packages..."
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq git curl ca-certificates python3 python3-pip python3-venv build-essential

if [ ! -x "$HOME/.elan/bin/elan" ]; then
  log "Installing elan..."
  curl https://elan.lean-lang.org/elan-init.sh -sSf | sh -s -- -y --default-toolchain none
fi
export PATH="$HOME/.elan/bin:$PATH"

log "Setting up a minimal project pinned to Mathlib v4.33.1..."
mkdir -p "$PROJECT_DIR"
cd "$PROJECT_DIR"
echo "leanprover/lean4:v4.33.1" > lean-toolchain
cat > lakefile.toml <<'EOF'
name = "pantograph_test_project"
defaultTargets = []

[[require]]
name = "mathlib"
scope = "leanprover-community"
rev = "v4.33.1"
EOF

log "Resolving dependencies (lake update)..."
lake update

log "Fetching prebuilt Mathlib cache (lake exe cache get)..."
t0=$(date +%s)
lake exe cache get
log "Cache fetch finished in $(( $(date +%s) - t0 ))s."

log "Building the (empty) project to finalize the Lake environment..."
lake build

log "Cloning PyPantograph and bumping its submodule to match v4.33.1..."
git clone --recurse-submodules https://github.com/stanford-centaur/PyPantograph.git "$PANTOGRAPH_SRC"
(cd "$PANTOGRAPH_SRC/src" && git fetch origin dev && git checkout "$PANTOGRAPH_SUBMODULE_REV")
log "PyPantograph's bundled toolchain: $(cat "$PANTOGRAPH_SRC/src/lean-toolchain")"

python3 -m venv "$HOME/venv"
# shellcheck source=/dev/null
source "$HOME/venv/bin/activate"

log "Installing PyPantograph (compiles the pantograph-repl binary, may take a few minutes)..."
t0=$(date +%s)
pip install -q "$PANTOGRAPH_SRC"
log "PyPantograph install finished in $(( $(date +%s) - t0 ))s."

log "Cloning lean-autoformalizer at ref '$BENCH_REF'..."
git clone --branch "$BENCH_REF" --single-branch https://github.com/javadnoorb/lean-autoformalizer.git "$REPO_DIR"
cd "$REPO_DIR/backend"
# PyPantograph is already installed above, from the version-matched clone
# (not requirements.txt -- see pantograph_sessions.py for why); this just
# adds the app's normal dependencies on top of it in the same venv.
pip install -q -r requirements.txt

export LEAN_PROJECT_DIR="$PROJECT_DIR"
export INTERACTIVE_MAX_SESSIONS=2
export ALLOW_MOCK_FALLBACK=true

log "Starting the backend..."
PYTHONPATH=. uvicorn app.main:app --host 127.0.0.1 --port 8000 > "$HOME/uvicorn.log" 2>&1 &
UVICORN_PID=$!
for _ in $(seq 1 30); do
  if curl -sf http://127.0.0.1:8000/api/status > /dev/null; then
    break
  fi
  sleep 1
done

log "GET /api/interactive/status (expect available:true)..."
curl -sf http://127.0.0.1:8000/api/interactive/status | tee /dev/stderr | grep -q '"available":true' \
  && log "OK: interactive API is available" || { log "FAIL: interactive API not available"; exit 1; }

log "POST /api/interactive/sessions (expect ~30s, the real Mathlib import)..."
t0=$(date +%s)
START_RESP=$(curl -sf -X POST http://127.0.0.1:8000/api/interactive/sessions \
  -H 'Content-Type: application/json' \
  -d '{"statement": "forall (a b : Nat), a + b = b + a"}')
log "Session start took $(( $(date +%s) - t0 ))s. Response: $START_RESP"
SESSION_ID=$(echo "$START_RESP" | python3 -c 'import json,sys; print(json.load(sys.stdin)["session_id"])')

log "POST tactic 'intro a b' (expect status:success)..."
curl -sf -X POST "http://127.0.0.1:8000/api/interactive/sessions/$SESSION_ID/tactic" \
  -H 'Content-Type: application/json' -d '{"tactic": "intro a b"}' | tee /dev/stderr \
  | grep -q '"status":"success"' && log "OK" || { log "FAIL"; exit 1; }

log "POST tactic 'exact Nat.add_comm a b' (expect is_solved:true, fast)..."
t1=$(date +%s%N)
curl -sf -X POST "http://127.0.0.1:8000/api/interactive/sessions/$SESSION_ID/tactic" \
  -H 'Content-Type: application/json' -d '{"tactic": "exact Nat.add_comm a b"}' | tee /dev/stderr \
  | grep -q '"is_solved":true' && log "OK" || { log "FAIL"; exit 1; }
log "Tactic call took $(( ($(date +%s%N) - t1) / 1000000 ))ms"

log "DELETE session (expect closed:true)..."
curl -sf -X DELETE "http://127.0.0.1:8000/api/interactive/sessions/$SESSION_ID" | tee /dev/stderr \
  | grep -q '"closed":true' && log "OK" || { log "FAIL"; exit 1; }

log "GET status again (expect active_sessions:0)..."
curl -sf http://127.0.0.1:8000/api/interactive/status | tee /dev/stderr \
  | grep -q '"active_sessions":0' && log "OK" || { log "FAIL"; exit 1; }

log "Negative check: 404 on a bogus session id..."
CODE=$(curl -s -o /dev/null -w '%{http_code}' -X POST "http://127.0.0.1:8000/api/interactive/sessions/does-not-exist/tactic" \
  -H 'Content-Type: application/json' -d '{"tactic": "foo"}')
[ "$CODE" = "404" ] && log "OK (got 404)" || { log "FAIL (got $CODE)"; exit 1; }

log "Negative check: 429 past INTERACTIVE_MAX_SESSIONS ($INTERACTIVE_MAX_SESSIONS)..."
for i in $(seq 1 "$INTERACTIVE_MAX_SESSIONS"); do
  curl -sf -X POST http://127.0.0.1:8000/api/interactive/sessions \
    -H 'Content-Type: application/json' \
    -d '{"statement": "forall (a b : Nat), a + b = b + a"}' > /dev/null
done
CODE=$(curl -s -o /dev/null -w '%{http_code}' -X POST http://127.0.0.1:8000/api/interactive/sessions \
  -H 'Content-Type: application/json' -d '{"statement": "forall (a b : Nat), a + b = b + a"}')
[ "$CODE" = "429" ] && log "OK (got 429)" || { log "FAIL (got $CODE)"; exit 1; }

log "All checks passed."
kill "$UVICORN_PID" 2>/dev/null || true
free -h
