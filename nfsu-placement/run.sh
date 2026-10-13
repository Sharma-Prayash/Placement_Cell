#!/usr/bin/env bash
# Starts Django (http://127.0.0.1:8000) and Vite (http://localhost:5173). Ctrl+C stops both.
set -euo pipefail
cd "$(dirname "$0")"
[ -d backend/.venv ] || { echo "Run ./setup.sh first."; exit 1; }
cleanup() { kill 0 2>/dev/null || true; }
trap cleanup EXIT INT TERM
( cd backend && set -a && . ./.env && set +a && .venv/bin/python manage.py runserver 127.0.0.1:8000 ) &
( cd frontend && npm run dev ) &
wait
