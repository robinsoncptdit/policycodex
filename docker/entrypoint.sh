#!/usr/bin/env sh
# DISC-01: first-boot SECRET_KEY + credential-store key generation.
# All persistent state lives under /data (the policycodex-data Docker volume).
# On a clean install both files are absent; we generate and write them once.
# Subsequent boots see the files and leave them alone.
set -e

DATA_DIR="${POLICYCODEX_DATA_DIR:-/data}"
mkdir -p "$DATA_DIR"

SECRET_KEY_FILE="$DATA_DIR/.secret-key"
CREDENTIAL_KEY_FILE="$DATA_DIR/.credential-key"

if [ ! -f "$SECRET_KEY_FILE" ]; then
    python3 -c "import secrets; print(secrets.token_urlsafe(50), end='')" > "$SECRET_KEY_FILE"
    chmod 600 "$SECRET_KEY_FILE"
fi

if [ ! -f "$CREDENTIAL_KEY_FILE" ]; then
    python3 -c "import os, base64; sys=__import__('sys'); sys.stdout.buffer.write(base64.urlsafe_b64encode(os.urandom(32)))" > "$CREDENTIAL_KEY_FILE"
    chmod 600 "$CREDENTIAL_KEY_FILE"
fi

# Django reads SECRET_KEY from this file (settings.py).
export POLICYCODEX_SECRET_KEY_FILE="$SECRET_KEY_FILE"
export POLICYCODEX_CREDENTIAL_KEY_FILE="$CREDENTIAL_KEY_FILE"

python3 manage.py migrate --noinput

exec gunicorn policycodex_site.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers 3
