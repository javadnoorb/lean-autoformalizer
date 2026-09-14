#!/usr/bin/env bash
# One-off benchmark: does PyPantograph's Server(imports=['Mathlib']) avoid
# the RAM-thrashing tax on a properly-sized cloud box, the way bare
# `import Mathlib` did in mathlib-bench.sh (1h08m locally -> 22s on an 8GB
# Vultr instance)? Locally, this exact call hung 35+ minutes on a 6GB-RAM
# box without ever reaching "ready" -- see
# .claude/skills/lean-interactive-search/SKILL.md for the full writeup.
#
# Same create/destroy/log/auto-destroy machinery as mathlib-bench.sh (see
# cloud-bench-lib.sh), its own label/plan/state file so the two benchmarks
# and the production app instance never collide. Skips harden-vm.sh for
# the same reason: this box only lives for the length of the test.
#
# Usage:
#   deploy/pantograph-bench.sh run          # create VM, run the test, auto-destroy when done
#   deploy/pantograph-bench.sh run --keep   # same, but leave the VM up afterward for inspection
#   deploy/pantograph-bench.sh destroy      # tear down the tracked benchmark VM
#   deploy/pantograph-bench.sh ssh          # SSH into the tracked benchmark VM
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Same reasoning as mathlib-bench.sh: 8GB comfortably covers the ~6GB
# Mathlib working set. Bump via BENCH_PLAN= if PyPantograph's extra
# overhead (over bare `lean`) turns out to need more.
export LABEL="lean-pantograph-bench"
export REGION="${BENCH_REGION:-ewr}"
export PLAN="${BENCH_PLAN:-vhf-3c-8gb}"
export STATE_FILE="$SCRIPT_DIR/.vultr-pantograph-bench-instance-id"
REMOTE_SCRIPT="$SCRIPT_DIR/pantograph-bench-remote.sh"
RESULTS_DIR="$SCRIPT_DIR/pantograph-bench-results"

# shellcheck source=cloud-bench-lib.sh
source "$SCRIPT_DIR/cloud-bench-lib.sh"
cloud_bench_dispatch "$@"
