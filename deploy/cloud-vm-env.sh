#!/usr/bin/env bash
# Locates the shared cloud-vm scripts (vultr-vm.sh, harden-vm.sh,
# cloud-bench-lib.sh), which live in their own repo so other projects can
# rent VMs the same way. Sourced by the deploy scripts here, not run directly.
CLOUD_VM_DIR="${CLOUD_VM_DIR:-$HOME/projects/cloud-vm}"
if [ ! -x "$CLOUD_VM_DIR/vultr-vm.sh" ]; then
  echo "cloud-vm scripts not found in $CLOUD_VM_DIR." >&2
  echo "Clone git@github.com:javadnoorb/cloud-vm.git there, or set CLOUD_VM_DIR." >&2
  exit 1
fi

# Keep using the SSH key already uploaded to Vultr under this name.
export SSH_KEY_NAME="${SSH_KEY_NAME:-$(hostname)-lean-autoformalizer}"
