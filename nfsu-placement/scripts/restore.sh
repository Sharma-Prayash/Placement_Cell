#!/usr/bin/env bash
# Restore drill: decrypt a backup into a scratch SQLite file and compare row counts with the live DB.
#   BACKUP_PASSPHRASE=... scripts/restore.sh backups/nfsu-YYYYmmdd-HHMMSS.sqlite3.enc
set -euo pipefail
cd "$(dirname "$0")/.."
: "${BACKUP_PASSPHRASE:?Set BACKUP_PASSPHRASE first}"
file=${1:?Pass the .enc backup file}
out=$(mktemp --suffix=.sqlite3)
openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 -in "$file" -out "$out" -pass env:BACKUP_PASSPHRASE
backend/.venv/bin/python - "$out" <<'PYEOF'
import sqlite3, sys
live, restored = sqlite3.connect("backend/db.sqlite3"), sqlite3.connect(sys.argv[1])
tables = [r[0] for r in restored.execute("select name from sqlite_master where type='table' and name not like 'sqlite_%'")]
bad = 0
for t in sorted(tables):
    a = live.execute(f'select count(*) from "{t}"').fetchone()[0]
    b = restored.execute(f'select count(*) from "{t}"').fetchone()[0]
    flag = "" if a == b else "  <- differs (expected if data changed after the backup)"
    bad += a != b
    print(f"{t:<40} live={a:<6} restored={b:<6}{flag}")
print("Restore drill complete." if not bad else f"{bad} table(s) differ.")
PYEOF
echo "Restored copy: $out"
