#!/usr/bin/env bash
# Runs ON the throwaway benchmark VM (as root, no hardening -- see
# pantograph-bench.sh for why). Sets up a minimal Mathlib project pinned to
# v4.33.1 -- the exact Lean version the local PyPantograph submodule fix
# was matched against (see .claude/skills/lean-interactive-search/SKILL.md)
# -- builds PyPantograph from that same fixed source, then times
# Server(imports=['Mathlib']) + goal_tactic the same way it was tested
# locally, where it hung 35+ minutes on a 6GB-RAM box without ever
# emitting "ready".
set -euo pipefail

PROJECT_DIR="$HOME/pantograph_test_project"
PANTOGRAPH_SRC="$HOME/PyPantograph"
# Commit of leanprover/Pantograph already verified locally to match Lean
# v4.33.1 exactly -- reusing it here skips re-deriving the version match.
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

cat > "$HOME/pantograph_test.py" <<PYEOF
import time
from pantograph.server import Server

t0 = time.time()
server = Server(imports=["Mathlib"], project_path="$PROJECT_DIR", timeout=600)
print("startup seconds:", time.time() - t0)

state0 = server.goal_start("forall (a b : Nat), a + b = b + a")
t1 = time.time()
# goal_start on a forall-statement leaves a/b un-introduced -- intro first.
state1 = server.goal_tactic(state0, tactic="intro a b")
state2 = server.goal_tactic(state1, tactic="exact Nat.add_comm a b")
print("tactic seconds:", time.time() - t1)
print("is_solved:", state2.is_solved)
PYEOF

log "Timing: Server(imports=['Mathlib']) + goal_start + goal_tactic..."
/usr/bin/time -v python3 "$HOME/pantograph_test.py" 2>&1 | tee "$HOME/pantograph-bench-result.log"

log "Done."
free -h
