#!/usr/bin/env bash
# One-time setup for macOS / Linux. Safe to re-run.
#   - Python packages go into backend/.venv only (nothing installed system-wide)
#   - JavaScript packages go into frontend/node_modules only
set -euo pipefail
cd "$(dirname "$0")"

say() { printf "\n\033[1m%s\033[0m\n" "$1"; }

say "Checking tools"
PY=${PYTHON:-python3}
command -v "$PY" >/dev/null || { echo "Python 3.11+ is required (python3 not found)."; exit 1; }
"$PY" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' || { echo "Python 3.11 or newer is required."; exit 1; }
command -v node >/dev/null || { echo "Node.js 18+ is required (node not found)."; exit 1; }
node -e 'process.exit(parseInt(process.versions.node) >= 18 ? 0 : 1)' || { echo "Node.js 18 or newer is required."; exit 1; }

say "Creating the Python virtual environment in backend/.venv"
if [ ! -d backend/.venv ]; then "$PY" -m venv backend/.venv; fi
VPY=backend/.venv/bin/python
"$VPY" -m pip install --quiet --upgrade pip
"$VPY" -m pip install --quiet -r backend/requirements.txt

if [ ! -f backend/.env ]; then
  say "Generating backend/.env with fresh secret keys"
  "$VPY" - <<'PYEOF'
import secrets
from cryptography.fernet import Fernet
words = ["ledger", "forensic", "cipher", "placement", "audit", "verify", "gandhinagar", "session"]
seed_pw = "-".join(secrets.choice(words) for _ in range(3)) + "-" + str(secrets.randbelow(9000) + 1000)
template = open("backend/.env.example").read()
values = {
    "DJANGO_SECRET_KEY": secrets.token_urlsafe(50),
    "FIELD_ENCRYPTION_KEY": Fernet.generate_key().decode(),
    "BLIND_INDEX_KEY": secrets.token_hex(32),
    "SEED_PASSWORD": seed_pw,
}
lines = []
for line in template.splitlines():
    key = line.split("=", 1)[0]
    lines.append(f"{key}={values[key]}" if key in values else line)
open("backend/.env", "w").write("\n".join(lines) + "\n")
PYEOF
  chmod 600 backend/.env
fi

say "Preparing the database"
( cd backend && .venv/bin/python manage.py migrate --verbosity 0 )
if ( cd backend && .venv/bin/python manage.py shell -c "from apps.students.models import Student; import sys; sys.exit(0 if Student.objects.exists() else 1)" ); then
  echo "Database already has data; skipping demo seed."
else
  ( cd backend && set -a && . ./.env && set +a && .venv/bin/python manage.py seed_demo )
fi

say "Installing frontend packages into frontend/node_modules"
( cd frontend && if [ -f package-lock.json ]; then npm ci --no-audit --no-fund; else npm install --no-audit --no-fund; fi )

say "Done."
echo "Demo password for every seeded account: $(grep '^SEED_PASSWORD=' backend/.env | cut -d= -f2-)"
echo "Start the app with:  ./run.sh   then open http://localhost:5173"
