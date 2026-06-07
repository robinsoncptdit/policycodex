# PolicyCodex application image (REPO-05). Generic and diocese-agnostic:
# per-diocese config enters at runtime via env + mounted volumes, never baked in.
FROM python:3.14-slim-bookworm

# git is required: the app shells out to git clone/push/pull for the
# diocese policy repo. The rest are slim-image build basics.
RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install Python deps first for layer caching.
COPY ai/requirements.txt ai/requirements.txt
COPY app/requirements.txt app/requirements.txt
RUN pip install --no-cache-dir -r ai/requirements.txt -r app/requirements.txt

# Copy the application source.
COPY . .

# Collect static assets at build time (served by WhiteNoise at runtime).
# A throwaway key satisfies settings import; DEBUG off is fine for collectstatic.
RUN DJANGO_SECRET_KEY=build-time-only python manage.py collectstatic --noinput

COPY docker/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

EXPOSE 8000
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
