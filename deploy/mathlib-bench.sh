#!/usr/bin/env bash
# One-off benchmark: does importing Mathlib on a properly-sized cloud box
# avoid the multi-hour RAM-thrashing tax measured locally (6GB RAM cap vs
# Mathlib's 6GB .olean footprint -- see
# .claude/skills/lean-interactive-search/SKILL.md for the full writeup)?
#
# Reuses vultr-vm.sh's create/destroy logic (same vultr-cli, same state-file
# pattern) with its own label/plan/state file so it never touches the
# tracked production instance. Deliberately skips harden-vm.sh: this box
# lives only as long as the test and is destroyed right after, so the
# extra minutes of ufw/fail2ban/deploy-user setup buy nothing here.
#
# Usage:
#   deploy/mathlib-bench.sh run          # create VM, run the test, auto-destroy when done
#   deploy/mathlib-bench.sh run --keep   # same, but leave the VM up afterward for inspection
#   deploy/mathlib-bench.sh destroy      # tear down the tracked benchmark VM
#   deploy/mathlib-bench.sh ssh          # SSH into the tracked benchmark VM
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# vhf-3c-8gb: Vultr's High Frequency line (faster per-core clock, which is
# what a mostly-single-threaded Lean elaboration benefits from) at 8GB RAM
# -- a bit over 2x the ~3.8GB peak RSS the same import actually used
# natively when it wasn't thrashing, without paying for a 32GB box that
# would sit mostly idle. Bump via BENCH_PLAN= if 8GB still isn't enough.
export LABEL="lean-mathlib-bench"
export REGION="${BENCH_REGION:-ewr}"
export PLAN="${BENCH_PLAN:-vhf-3c-8gb}"
export STATE_FILE="$SCRIPT_DIR/.vultr-bench-instance-id"
REMOTE_SCRIPT="$SCRIPT_DIR/mathlib-bench-remote.sh"
RESULTS_DIR="$SCRIPT_DIR/mathlib-bench-results"

# shellcheck source=cloud-bench-lib.sh
source "$SCRIPT_DIR/cloud-bench-lib.sh"
cloud_bench_dispatch "$@"
