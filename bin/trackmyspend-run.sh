#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VENV="${ROOT}/.venv/bin"
SMS_DIR="${ROOT}/mobile_companion_app/test_server"

cd "$ROOT"

# ponytail: if any child exits, kill all and let systemd Restart= bring the stack back
trap 'kill 0' EXIT INT TERM

# Main API (port 2006)
"${VENV}/uvicorn" src.app:app \
  --host 0.0.0.0 --port 2006 \
  --access-log false &

# Frontend UI (port 2007)
"${VENV}/python" -m http.server 2007 --directory "${ROOT}/frontend" &

# SMS companion ingest server (port 2005)
cd "${SMS_DIR}"
"${VENV}/uvicorn" main:app \
  --host 0.0.0.0 --port 2005 &

wait -n
exit 1
