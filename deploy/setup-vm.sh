#!/usr/bin/env bash
# One-time setup for a fresh Ubuntu Vultr instance running the mock-mode app.
# Usage: ssh into the VM, then run this script.
set -euo pipefail

REPO_URL="git@github.com:javadnoorb/lean-autoformalizer.git"
REPO_DIR="$HOME/lean-autoformalizer"

# Install Docker + Compose plugin
if ! command -v docker &>/dev/null; then
  curl -fsSL https://get.docker.com | sudo sh
  sudo usermod -aG docker "$USER"
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

sudo docker compose up -d --build
echo "App running: frontend on port 80, backend proxied at /api"
