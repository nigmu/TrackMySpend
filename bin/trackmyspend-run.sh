#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VENV="${ROOT}/.venv/bin"

cd "$ROOT"

# ponytail: if any child exits, kill all and let systemd Restart= bring the stack back
trap 'kill 0' EXIT INT TERM

# Main API (port 2006) — Gmail, SMS ingest, companion OTA
"${VENV}/uvicorn" src.app:app \
  --host 0.0.0.0 --port 2006 \
  --access-log false &

# Frontend UI (port 2007)
"${VENV}/python" -m http.server 2007 --directory "${ROOT}/frontend" &

wait -n
exit 1
