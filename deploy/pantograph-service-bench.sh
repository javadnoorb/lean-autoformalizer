#!/usr/bin/env bash
# End-to-end verification of the /api/interactive/* endpoints
# (backend/app/services/pantograph_sessions.py) against real Mathlib on
# properly-sized hardware -- this can never be exercised on the local dev
# machine (6GB RAM cap). Same throwaway-VM pattern as mathlib-bench.sh /
# pantograph-bench.sh (see cloud-bench-lib.sh), its own label/state file so
# none of the three benchmarks or the production app instance can collide.
# Skips harden-vm.sh for the same reason as the other benches: this box
# only lives for the length of the test.
#
# Usage:
#   deploy/pantograph-service-bench.sh run          # create VM, run the test, auto-destroy when done
#   deploy/pantograph-service-bench.sh run --keep   # same, but leave the VM up afterward
#   deploy/pantograph-service-bench.sh destroy      # tear down the tracked benchmark VM
#   deploy/pantograph-service-bench.sh ssh          # SSH into a --keep'd VM
#
# BENCH_REF (env var, default: current branch) selects which git ref of
# this repo gets deployed on the VM.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

export LABEL="lean-interactive-api-bench"
export REGION="${BENCH_REGION:-ewr}"
export PLAN="${BENCH_PLAN:-vhf-3c-8gb}"
export STATE_FILE="$SCRIPT_DIR/.vultr-interactive-api-bench-instance-id"
BENCH_REF="${BENCH_REF:-$(git -C "$SCRIPT_DIR" rev-parse --abbrev-ref HEAD)}"
export REMOTE_ENV_EXPORTS="BENCH_REF='$BENCH_REF'"
REMOTE_SCRIPT="$SCRIPT_DIR/pantograph-service-bench-remote.sh"
RESULTS_DIR="$SCRIPT_DIR/pantograph-service-bench-results"

# shellcheck source=cloud-bench-lib.sh
source "$SCRIPT_DIR/cloud-bench-lib.sh"
cloud_bench_dispatch "$@"
