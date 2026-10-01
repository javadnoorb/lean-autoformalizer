#!/usr/bin/env bash
# Shared orchestration for one-off Vultr benchmark scripts (mathlib-bench.sh,
# pantograph-bench.sh): provision a VM via vultr-vm.sh, stream a remote
# script's output back over SSH into a local timestamped log (the durable
# record, since the VM and its own copy disappear at teardown), auto-destroy
# on exit unless --keep is passed. Sourced, not run directly -- the caller
# must set LABEL, PLAN, REGION, STATE_FILE, SCRIPT_DIR, REMOTE_SCRIPT,
# RESULTS_DIR before sourcing this file.
set -euo pipefail

wait_for_ssh() {
  local ip="$1"
  echo "Waiting for SSH on $ip..." >&2
  for _ in $(seq 1 30); do
    if ssh -o StrictHostKeyChecking=accept-new -o ConnectTimeout=5 \
        -o BatchMode=yes "root@$ip" true 2>/dev/null; then
      return 0
    fi
    sleep 5
  done
  echo "Timed out waiting for SSH." >&2
  exit 1
}

cloud_bench_run() {
  local keep=0
  [ "${1:-}" = "--keep" ] && keep=1

  # Auto-destroy on any exit (success, failure, or Ctrl-C) unless --keep
  # was passed -- the real cost risk here is forgetting to destroy a
  # billed instance, not destroying one too eagerly.
  if [ "$keep" -eq 0 ]; then
    trap '[ -f "$STATE_FILE" ] && { echo "Auto-destroying benchmark VM..." >&2; "$SCRIPT_DIR/vultr-vm.sh" destroy; }' EXIT
  fi

  local ip
  ip=$("$SCRIPT_DIR/vultr-vm.sh" create)

  wait_for_ssh "$ip"

  mkdir -p "$RESULTS_DIR"
  local log_file="$RESULTS_DIR/$(date +%Y%m%d-%H%M%S).log"

  echo "Running the benchmark on $ip (this streams live)..." >&2
  echo "Logging to $log_file" >&2
  ssh -o StrictHostKeyChecking=accept-new "root@$ip" 'bash -s' \
    < "$REMOTE_SCRIPT" | tee "$log_file"

  if [ "$keep" -eq 1 ]; then
    cat <<EOF

Done. Results saved to $log_file
VM is still running at root@$ip for inspection (--keep was passed).
Tear it down when finished (billing continues until you do):
  $0 destroy
EOF
  else
    echo "Done. Results saved to $log_file. Destroying the VM now." >&2
  fi
}

cloud_bench_ssh() {
  if [ ! -f "$STATE_FILE" ]; then
    echo "No tracked benchmark instance. Run '$0 run' first." >&2
    exit 1
  fi
  local ip
  ip=$(sed -n '2p' "$STATE_FILE")
  ssh "root@$ip"
}

cloud_bench_destroy() {
  "$SCRIPT_DIR/vultr-vm.sh" destroy
}

cloud_bench_dispatch() {
  case "${1:-}" in
    run) cloud_bench_run "${2:-}" ;;
    ssh) cloud_bench_ssh ;;
    destroy) cloud_bench_destroy ;;
    *)
      echo "Usage: $0 {run [--keep]|ssh|destroy}" >&2
      exit 1
      ;;
  esac
}
