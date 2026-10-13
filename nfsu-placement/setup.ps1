# One-time setup for Windows (PowerShell). Run:  powershell -ExecutionPolicy Bypass -File setup.ps1
# Python packages go into backend\.venv only; JavaScript packages into frontend\node_modules only.
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

function Say($m) { Write-Host "`n$m" -ForegroundColor Cyan }

Say "Checking tools"
$py = if (Get-Command py -ErrorAction SilentlyContinue) { "py" } elseif (Get-Command python -ErrorAction SilentlyContinue) { "python" } else { throw "Python 3.11+ is required." }
& $py -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)"
if ($LASTEXITCODE -ne 0) { throw "Python 3.11 or newer is required." }
if (-not (Get-Command node -ErrorAction SilentlyContinue)) { throw "Node.js 18+ is required." }

Say "Creating the Python virtual environment in backend\.venv"
if (-not (Test-Path backend\.venv)) { & $py -m venv backend\.venv }
$vpy = "backend\.venv\Scripts\python.exe"
& $vpy -m pip install --quiet --upgrade pip
& $vpy -m pip install --quiet -r backend\requirements.txt

if (-not (Test-Path backend\.env)) {
  Say "Generating backend\.env with fresh secret keys"
  & $vpy -c @"
import secrets
from cryptography.fernet import Fernet
words = ['ledger', 'forensic', 'cipher', 'placement', 'audit', 'verify', 'gandhinagar', 'session']
seed_pw = '-'.join(secrets.choice(words) for _ in range(3)) + '-' + str(secrets.randbelow(9000) + 1000)
values = {'DJANGO_SECRET_KEY': secrets.token_urlsafe(50), 'FIELD_ENCRYPTION_KEY': Fernet.generate_key().decode(),
          'BLIND_INDEX_KEY': secrets.token_hex(32), 'SEED_PASSWORD': seed_pw}
out = []
for line in open('backend/.env.example').read().splitlines():
    key = line.split('=', 1)[0]
    out.append(f'{key}={values[key]}' if key in values else line)
open('backend/.env', 'w').write('\n'.join(out) + '\n')
"@
}

Say "Preparing the database"
Push-Location backend
& .venv\Scripts\python.exe manage.py migrate --verbosity 0
& .venv\Scripts\python.exe manage.py shell -c "from apps.students.models import Student; import sys; sys.exit(0 if Student.objects.exists() else 1)"
if ($LASTEXITCODE -ne 0) { & .venv\Scripts\python.exe manage.py seed_demo }
Pop-Location

Say "Installing frontend packages into frontend\node_modules"
Push-Location frontend
if (Test-Path package-lock.json) { npm ci --no-audit --no-fund } else { npm install --no-audit --no-fund }
Pop-Location

$pw = (Select-String -Path backend\.env -Pattern '^SEED_PASSWORD=(.*)$').Matches[0].Groups[1].Value
Say "Done."
Write-Host "Demo password for every seeded account: $pw"
Write-Host "Start the app with:  powershell -ExecutionPolicy Bypass -File run.ps1   then open http://localhost:5173"
