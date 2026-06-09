#!/usr/bin/env sh
set -e

# Pull secrets from the /secrets/config.env bind mount (~/.config/policycodex/
# on the host, REPO-05) into the process env BEFORE migrate/gunicorn so the
# LLM SDKs and any env-driven Django config see them (REPO-17). `|| true`
# keeps a malformed line in the user's config.env logged-but-non-fatal so
# the container still boots; well-formed assignments up to the bad line do
# get exported (POSIX `.` is line-by-line).
. /usr/local/bin/load-secrets.sh || true

# Apply migrations against the (volume-backed) database.
python manage.py migrate --noinput

# Create the admin user only when all three env vars are supplied. Django's
# createsuperuser --noinput reads DJANGO_SUPERUSER_USERNAME / _EMAIL /
# _PASSWORD from the environment, and requires all three (email is a
# REQUIRED_FIELD). The `|| true` tolerates re-runs where the user exists.
if [ -n "$DJANGO_SUPERUSER_USERNAME" ] && [ -n "$DJANGO_SUPERUSER_EMAIL" ] && [ -n "$DJANGO_SUPERUSER_PASSWORD" ]; then
    python manage.py createsuperuser --noinput || true
fi

exec gunicorn policycodex_site.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers 3
