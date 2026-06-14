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

# DISC-01: collectstatic does not need a real SECRET_KEY; pass a dummy.
RUN DJANGO_SECRET_KEY=build-time-only-dummy python manage.py collectstatic --noinput

COPY docker/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

# Documentation only: the default port. The actual bind is set at runtime from
# POLICYCODEX_PORT (entrypoint.sh + compose port mapping), so a custom port works
# without rebuilding; EXPOSE has no runtime effect and stays at the default.
EXPOSE 8000
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
