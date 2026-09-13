#!/usr/bin/env bash
# End-to-end deploy: create the VM, harden it, install Docker, and bring the
# app up over HTTPS — a single command instead of the manual multi-step flow.
#
# Usage:
#   deploy/deploy.sh
#
# The Gemini API key is resolved automatically, in this order:
#   1. $GEMINI_API_KEY               (the key itself)
#   2. $GEMINI_API_KEY_FILE          (path to a file containing just the key)
#   3. ~/.config/lean-autoformalizer/gemini-api-key (default file location)
#
# If none of those are found, the app still comes up (mock mode still
# works), but formalization calls will fail until you SSH in and set
# GEMINI_API_KEY in backend/.env yourself.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_USER="${DEPLOY_USER:-deploy}"
DEFAULT_KEY_FILE="$HOME/.config/lean-autoformalizer/gemini-api-key"
SSH_OPTS=(-o StrictHostKeyChecking=accept-new -o ConnectTimeout=8)

resolve_gemini_key() {
  if [ -n "${GEMINI_API_KEY:-}" ]; then
    printf '%s' "$GEMINI_API_KEY"
  elif [ -n "${GEMINI_API_KEY_FILE:-}" ] && [ -f "$GEMINI_API_KEY_FILE" ]; then
    head -1 "$GEMINI_API_KEY_FILE"
  elif [ -f "$DEFAULT_KEY_FILE" ]; then
    head -1 "$DEFAULT_KEY_FILE"
  fi
}

echo "==> Creating VM..."
ip=$("$SCRIPT_DIR/vultr-vm.sh" create)
echo "VM IP: $ip"

echo "==> Waiting for SSH..."
for _ in $(seq 1 30); do
  ssh "${SSH_OPTS[@]}" -o BatchMode=yes "root@$ip" true 2>/dev/null && break
  sleep 5
done

echo "==> Hardening..."
ssh "${SSH_OPTS[@]}" "root@$ip" 'bash -s' < "$SCRIPT_DIR/harden-vm.sh"

echo "==> Installing Docker..."
ssh "${SSH_OPTS[@]}" "$DEPLOY_USER@$ip" '
  command -v docker &>/dev/null || {
    curl -fsSL https://get.docker.com | sudo sh
    sudo usermod -aG docker "$USER"
  }
'

echo "==> Cloning the repo..."
ssh "${SSH_OPTS[@]}" "$DEPLOY_USER@$ip" '
  set -euo pipefail
  REPO_URL="https://github.com/javadnoorb/lean-autoformalizer.git"
  REPO_DIR="$HOME/lean-autoformalizer"
  if [ -d "$REPO_DIR" ]; then
    git -C "$REPO_DIR" pull
  else
    git clone "$REPO_URL" "$REPO_DIR"
  fi
  [ -f "$REPO_DIR/backend/.env" ] || cp "$REPO_DIR/backend/.env.example" "$REPO_DIR/backend/.env"
'

key="$(resolve_gemini_key || true)"
if [ -n "$key" ]; then
  echo "==> Setting GEMINI_API_KEY from local environment/file..."
  # Piped over stdin (not a command-line arg) so the key never appears in
  # `ps` output on either end.
  printf '%s' "$key" | ssh "${SSH_OPTS[@]}" "$DEPLOY_USER@$ip" '
    read -r k
    sed -i "s|^GEMINI_API_KEY=.*|GEMINI_API_KEY=$k|" ~/lean-autoformalizer/backend/.env
  '
else
  echo "==> No local Gemini API key found (checked \$GEMINI_API_KEY, \$GEMINI_API_KEY_FILE, $DEFAULT_KEY_FILE)."
  echo "    Formalization calls will fail until you set one:"
  echo "    ssh $DEPLOY_USER@$ip"
  echo "    nano ~/lean-autoformalizer/backend/.env"
fi

echo "==> Building and starting containers..."
ssh "${SSH_OPTS[@]}" "$DEPLOY_USER@$ip" 'cd ~/lean-autoformalizer && bash deploy/setup-vm.sh'
