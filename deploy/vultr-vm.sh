#!/usr/bin/env bash
# Create or destroy the Vultr VM used to host lean-autoformalizer.
#
# Usage:
#   deploy/vultr-vm.sh create   # provision a new VM, print its IP
#   deploy/vultr-vm.sh status   # show the tracked VM
#   deploy/vultr-vm.sh destroy  # tear down the tracked VM
#
# A thin wrapper over the shared cloud-vm repo's vultr-vm.sh (see
# cloud-vm-env.sh), with this app's label and state file. LABEL, PLAN,
# REGION etc. can still be overridden by env var.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=cloud-vm-env.sh
source "$SCRIPT_DIR/cloud-vm-env.sh"

export LABEL="${LABEL:-lean-autoformalizer}"
export STATE_FILE="${STATE_FILE:-$SCRIPT_DIR/.vultr-instance-id}"
exec "$CLOUD_VM_DIR/vultr-vm.sh" "$@"
