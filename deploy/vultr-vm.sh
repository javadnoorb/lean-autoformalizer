#!/usr/bin/env bash
# Create or destroy the Vultr VM used to host lean-autoformalizer.
#
# Usage:
#   deploy/vultr-vm.sh create   # provision a new VM, print its IP
#   deploy/vultr-vm.sh destroy  # tear down the tracked VM
#
# Requires: vultr-cli (https://github.com/vultr/vultr-cli) configured with a
# valid API key (~/.vultr-cli.yaml or VULTR_API_KEY env var).
set -euo pipefail

LABEL="lean-autoformalizer"
REGION="ewr"
PLAN="vc2-1c-1gb"
OS_ID=2284 # Ubuntu 24.04 LTS x64
SSH_KEY_NAME="${SSH_KEY_NAME:-$(hostname)-lean-autoformalizer}"
SSH_PUBKEY_FILE="${SSH_PUBKEY_FILE:-$HOME/.ssh/id_ed25519.pub}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STATE_FILE="$SCRIPT_DIR/.vultr-instance-id"

require_cli() {
  command -v vultr-cli &>/dev/null || {
    echo "vultr-cli not found. Install it from https://github.com/vultr/vultr-cli" >&2
    exit 1
  }
}

find_or_upload_ssh_key() {
  local key_id
  key_id=$(vultr-cli ssh-key list | awk -v name="$SSH_KEY_NAME" '$0 ~ name {print $1; exit}')
  if [ -z "$key_id" ]; then
    echo "Uploading SSH key '$SSH_KEY_NAME'..." >&2
    key_id=$(vultr-cli ssh-key create --name "$SSH_KEY_NAME" --key "$(cat "$SSH_PUBKEY_FILE")" \
      | awk 'NR==2 {print $1}')
  fi
  echo "$key_id"
}

cmd_create() {
  require_cli

  if [ -f "$STATE_FILE" ]; then
    echo "A tracked instance already exists ($(head -1 "$STATE_FILE")). Run 'destroy' first." >&2
    exit 1
  fi

  local ssh_key_id
  ssh_key_id=$(find_or_upload_ssh_key)

  echo "Creating $PLAN instance in $REGION..." >&2
  local instance_id
  instance_id=$(vultr-cli instance create \
    --region="$REGION" \
    --plan="$PLAN" \
    --os="$OS_ID" \
    --label="$LABEL" \
    --host="$LABEL" \
    --ssh-keys="$ssh_key_id" \
    | awk 'NR==2 {print $1}')

  echo "$instance_id" > "$STATE_FILE"
  echo "Instance created: $instance_id" >&2

  echo "Waiting for it to boot..." >&2
  local ip status
  for _ in $(seq 1 30); do
    ip=$(vultr-cli instance get "$instance_id" | awk '/MAIN IP/ {print $3}')
    status=$(vultr-cli instance get "$instance_id" | awk '/^STATUS/ {print $2}')
    if [ "$status" = "active" ] && [ "$ip" != "0.0.0.0" ]; then
      echo "$ip" >> "$STATE_FILE"
      echo "VM ready at $ip" >&2
      echo "$ip"
      return 0
    fi
    sleep 10
  done

  echo "Timed out waiting for the VM to become active. Check 'vultr-cli instance get $instance_id'." >&2
  exit 1
}

cmd_destroy() {
  require_cli

  if [ ! -f "$STATE_FILE" ]; then
    echo "No tracked instance found ($STATE_FILE missing)." >&2
    exit 1
  fi

  local instance_id
  instance_id=$(head -1 "$STATE_FILE")
  echo "Destroying instance $instance_id..." >&2
  vultr-cli instance delete "$instance_id"
  rm -f "$STATE_FILE"
  echo "Destroyed." >&2
}

cmd_status() {
  require_cli
  if [ ! -f "$STATE_FILE" ]; then
    echo "No tracked instance."
    exit 0
  fi
  vultr-cli instance get "$(head -1 "$STATE_FILE")"
}

case "${1:-}" in
  create) cmd_create ;;
  destroy) cmd_destroy ;;
  status) cmd_status ;;
  *)
    echo "Usage: $0 {create|destroy|status}" >&2
    exit 1
    ;;
esac
