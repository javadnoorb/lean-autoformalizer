#!/usr/bin/env bash
# Run the app locally (native backend + Vite dev server) so you can check it
# in a browser, without touching Docker or a VM.
#
# Usage:
#   deploy/local-deploy.sh [start|stop|status]   (default: start)
#
# start:  creates the backend venv (first run only), installs deps, and
#         launches uvicorn + the Vite dev server in the background.
# stop:   kills both background processes.
# status: shows whether they're running and hits /api/status.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
STATE_DIR="$ROOT_DIR/deploy/.local-deploy"
BACKEND_PID_FILE="$STATE_DIR/backend.pid"
FRONTEND_PID_FILE="$STATE_DIR/frontend.pid"
BACKEND_LOG="$STATE_DIR/backend.log"
FRONTEND_LOG="$STATE_DIR/frontend.log"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-3000}"

is_running() {
  local pid_file="$1"
  [ -f "$pid_file" ] && kill -0 "$(cat "$pid_file")" 2>/dev/null
}

print_urls() {
  echo "  Local:    http://localhost:$FRONTEND_PORT"
  local tailscale_ip
  tailscale_ip="$(tailscale ip -4 2>/dev/null || true)"
  [ -n "$tailscale_ip" ] && echo "  Tailscale: http://$tailscale_ip:$FRONTEND_PORT"
}

cmd_start() {
  mkdir -p "$STATE_DIR"

  if is_running "$BACKEND_PID_FILE"; then
    echo "Backend already running (pid $(cat "$BACKEND_PID_FILE"))."
  else
    echo "==> Setting up backend..."
    cd "$ROOT_DIR/backend"
    [ -f .env ] || cp .env.example .env
    [ -d .venv ] || python3 -m venv .venv
    source .venv/bin/activate
    pip install -q -r requirements.txt

    echo "==> Starting backend on :$BACKEND_PORT..."
    setsid uvicorn app.main:app --host 0.0.0.0 --port "$BACKEND_PORT" \
      > "$BACKEND_LOG" 2>&1 < /dev/null &
    echo $! > "$BACKEND_PID_FILE"
    deactivate
    cd "$ROOT_DIR"
  fi

  if is_running "$FRONTEND_PID_FILE"; then
    echo "Frontend already running (pid $(cat "$FRONTEND_PID_FILE"))."
  else
    echo "==> Setting up frontend..."
    cd "$ROOT_DIR/frontend"
    [ -d node_modules ] || npm install

    echo "==> Starting frontend on :$FRONTEND_PORT..."
    setsid npm run dev -- --host 0.0.0.0 --port "$FRONTEND_PORT" \
      > "$FRONTEND_LOG" 2>&1 < /dev/null &
    echo $! > "$FRONTEND_PID_FILE"
    cd "$ROOT_DIR"
  fi

  echo "==> Waiting for backend..."
  for _ in $(seq 1 30); do
    curl -fsS "http://localhost:$BACKEND_PORT/api/status" >/dev/null 2>&1 && break
    sleep 1
  done

  echo
  echo "App is up:"
  print_urls
  echo
  echo "Logs: $BACKEND_LOG, $FRONTEND_LOG"
  echo "Stop with: deploy/local-deploy.sh stop"
}

cmd_stop() {
  for pid_file in "$BACKEND_PID_FILE" "$FRONTEND_PID_FILE"; do
    if is_running "$pid_file"; then
      # setsid made the pid its own process group leader, so -pid kills the
      # whole tree (e.g. `npm run dev` -> `sh -c vite` -> the vite node process).
      kill -- "-$(cat "$pid_file")"
      rm -f "$pid_file"
    fi
  done
  echo "Stopped."
}

cmd_status() {
  if is_running "$BACKEND_PID_FILE"; then
    echo "Backend running (pid $(cat "$BACKEND_PID_FILE"))"
  else
    echo "Backend not running"
  fi
  if is_running "$FRONTEND_PID_FILE"; then
    echo "Frontend running (pid $(cat "$FRONTEND_PID_FILE"))"
  else
    echo "Frontend not running"
  fi
  echo
  curl -fsS "http://localhost:$BACKEND_PORT/api/status" 2>/dev/null || echo "Backend not responding."
  echo
  print_urls
}

case "${1:-start}" in
  start) cmd_start ;;
  stop) cmd_stop ;;
  status) cmd_status ;;
  *) echo "Usage: $0 [start|stop|status]" >&2; exit 1 ;;
esac
