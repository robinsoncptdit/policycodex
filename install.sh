#!/usr/bin/env bash
# PolicyCodex one-command install (REPO-05). Builds and starts the stack
# from source (Profile A). Run from the repo root: ./install.sh
set -euo pipefail

if ! command -v docker >/dev/null 2>&1; then
    echo "Error: docker is not installed. Install Docker first: https://docs.docker.com/get-docker/" >&2
    exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
    echo "Error: 'docker compose' (v2) is required." >&2
    exit 1
fi

if [ ! -f .env ]; then
    cp .env.example .env
    echo "Created .env from .env.example. Edit it to set DJANGO_SECRET_KEY and your"
    echo "diocese values, then re-run ./install.sh. Secrets stay in ~/.config/policycodex/."
    exit 0
fi

echo "Building and starting PolicyCodex (this may take a few minutes the first time)..."
docker compose up --build -d

echo
echo "PolicyCodex is starting at http://localhost:8000"
echo "Complete the onboarding wizard in your browser, or run the AI inventory pass."
echo "Logs: docker compose logs -f"
