#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
backend_pid=""

stop_backend() {
  if [[ -n "$backend_pid" ]] && kill -0 "$backend_pid" 2>/dev/null; then
    kill "$backend_pid"
    wait "$backend_pid" 2>/dev/null || true
  fi
}
trap stop_backend EXIT INT TERM

cd "$project_root"
PYTHONPATH="$project_root/src${PYTHONPATH:+:$PYTHONPATH}" \
  python3 -m trio.main &
backend_pid=$!

sleep 1
if ! kill -0 "$backend_pid" 2>/dev/null; then
  echo "Trio backend failed to start." >&2
  exit 1
fi

cd "$project_root/ui"
npm run dev
