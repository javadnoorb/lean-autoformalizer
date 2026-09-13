#!/usr/bin/env bash
# Setup for the app on a hardened Vultr instance (run harden-vm.sh first).
# Usage: ssh in as the deploy user, then run this script.
set -euo pipefail

REPO_URL="https://github.com/javadnoorb/lean-autoformalizer.git"
REPO_DIR="$HOME/lean-autoformalizer"

# Install Docker + Compose plugin
if ! command -v docker &>/dev/null; then
  curl -fsSL https://get.docker.com | sudo sh
  sudo usermod -aG docker "$USER"
  echo "Added $USER to the docker group. Log out and back in, then rerun this script."
  exit 0
fi

# Clone or update the repo
if [ -d "$REPO_DIR" ]; then
  git -C "$REPO_DIR" pull
else
  git clone "$REPO_URL" "$REPO_DIR"
fi

cd "$REPO_DIR"

if [ ! -f backend/.env ]; then
  cp backend/.env.example backend/.env
  echo "Edit $REPO_DIR/backend/.env to set your GEMINI_API_KEY, then rerun this script."
  exit 1
fi

# Generate the Caddyfile from this VM's current public IP via sslip.io, so a
# freshly (re)created VM with a new IP gets a matching HTTPS hostname without
# any manual editing.
public_ip=$(curl -fsS https://api.ipify.org)
domain="$(echo "$public_ip" | tr '.' '-').sslip.io"
sed "s/{{DOMAIN}}/$domain/" Caddyfile.template > Caddyfile

docker compose up -d --build
echo "App running at https://$domain"
