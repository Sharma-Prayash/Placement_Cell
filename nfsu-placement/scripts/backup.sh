#!/usr/bin/env bash
# Encrypted backup. SQLite: copies the DB file. Postgres: pg_dump. Output is AES-256 encrypted with
# a passphrase from $BACKUP_PASSPHRASE (keep it outside the repo).
set -euo pipefail
cd "$(dirname "$0")/.."
: "${BACKUP_PASSPHRASE:?Set BACKUP_PASSPHRASE first}"
mkdir -p backups
stamp=$(date +%Y%m%d-%H%M%S)
src=$(mktemp)
if grep -q '^DB_ENGINE=postgres' backend/.env; then
  set -a; . backend/.env; set +a
  PGPASSWORD="$POSTGRES_PASSWORD" pg_dump -h "$POSTGRES_HOST" -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc > "$src"
  ext=pgdump
else
  backend/.venv/bin/python -c "import sqlite3,sys; s=sqlite3.connect('backend/db.sqlite3'); d=sqlite3.connect(sys.argv[1]); s.backup(d)" "$src"
  ext=sqlite3
fi
openssl enc -aes-256-cbc -pbkdf2 -iter 200000 -salt -in "$src" -out "backups/nfsu-$stamp.$ext.enc" -pass env:BACKUP_PASSPHRASE
rm -f "$src"
echo "Wrote backups/nfsu-$stamp.$ext.enc"
