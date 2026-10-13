#!/usr/bin/env bash
# Runs the backend test suite (policy case table + attack tests) and a frontend type-check.
set -euo pipefail
cd "$(dirname "$0")"
( cd backend && set -a && . ./.env && set +a && .venv/bin/python manage.py test tests "$@" )
( cd frontend && npx tsc -b --noEmit && echo "Frontend type-check passed." )
