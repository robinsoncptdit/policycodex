#!/usr/bin/env sh
set -e

# Apply migrations against the (volume-backed) database.
python manage.py migrate --noinput

# Create the admin user only when all three env vars are supplied and the
# user does not already exist. Django's createsuperuser --noinput reads
# DJANGO_SUPERUSER_USERNAME / _EMAIL / _PASSWORD from the environment.
if [ -n "$DJANGO_SUPERUSER_USERNAME" ] && [ -n "$DJANGO_SUPERUSER_PASSWORD" ]; then
    python manage.py createsuperuser --noinput || true
fi

exec gunicorn policycodex_site.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers 3
