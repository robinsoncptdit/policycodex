#!/usr/bin/env sh
# DISC-15: PolicyCodex installer for Profile A (source clone).
# Builds the container image, starts it detached, waits for /health/,
# then opens the host's default browser at http://localhost:8000.
set -e

PORT="${POLICYCODEX_PORT:-8000}"

if ! command -v docker >/dev/null 2>&1; then
    echo "Docker is required. Install Docker Desktop or Engine and re-run."
    exit 1
fi

# docker-compose.yml declares env_file: .env. On a fresh clone the file
# doesn't exist yet; seed it from the committed example so compose loads.
if [ ! -f .env ]; then
    cp .env.example .env
fi

docker compose up --build -d

echo "Waiting for PolicyCodex to come up..."
for i in $(seq 1 30); do
    if curl -fsS "http://localhost:${PORT}/health/" >/dev/null 2>&1; then
        break
    fi
    sleep 2
done

URL="http://localhost:${PORT}/"
case "$(uname -s)" in
    Darwin*) open "$URL" ;;
    Linux*)  xdg-open "$URL" 2>/dev/null || true ;;
    *)       echo "Open ${URL} in your browser." ;;
esac

echo "PolicyCodex is running at ${URL}"
