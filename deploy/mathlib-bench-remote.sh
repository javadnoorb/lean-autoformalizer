#!/usr/bin/env bash
# Runs ON the throwaway benchmark VM (as root, no hardening -- see
# mathlib-bench.sh for why). Installs the Lean toolchain, fetches Mathlib
# from the community's prebuilt .olean cache (falling back to a from-source
# build only if the cache doesn't cover it), then times a bare `import
# Mathlib` -- the same measurement taken locally that showed 1h08m and
# heavy thrashing on a 6GB-RAM box. Point of the exercise: confirm that
# more RAM alone fixes it, without any change to the Lean/Mathlib side.
set -euo pipefail

MATHLIB_DIR="$HOME/mathlib4"

log() { echo "[$(date +%H:%M:%S)] $*"; }

log "Installing base packages..."
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq git curl ca-certificates

if [ ! -x "$HOME/.elan/bin/elan" ]; then
  log "Installing elan..."
  curl https://elan.lean-lang.org/elan-init.sh -sSf | sh -s -- -y --default-toolchain none
fi
export PATH="$HOME/.elan/bin:$PATH"

if [ ! -d "$MATHLIB_DIR" ]; then
  log "Cloning mathlib4 (shallow, latest master)..."
  git clone --depth 1 https://github.com/leanprover-community/mathlib4 "$MATHLIB_DIR"
fi
cd "$MATHLIB_DIR"

log "Lean toolchain pinned by this checkout: $(cat lean-toolchain)"

log "Fetching prebuilt Mathlib cache (lake exe cache get)..."
t0=$(date +%s)
if lake exe cache get; then
  log "Cache fetch succeeded in $(( $(date +%s) - t0 ))s."
else
  log "Cache fetch failed or incomplete -- falling back to a from-source build."
  log "This will take much longer; it is not the scenario being measured."
  lake build Mathlib
  log "Build finished in $(( $(date +%s) - t0 ))s."
fi

echo 'import Mathlib' > BenchImport.lean

log "Timing: lake env lean BenchImport.lean (bare 'import Mathlib')..."
/usr/bin/time -v lake env lean BenchImport.lean 2>&1 | tee "$HOME/mathlib-bench-result.log"

log "Done. Full resource stats saved on the VM at ~/mathlib-bench-result.log"
free -h
