#!/usr/bin/env sh
# Source secrets from /secrets/config.env (the ~/.config/policycodex/ bind
# mount per REPO-05) into the process env. No-op when the file is absent
# or empty so the container still boots without credentials configured
# (login + the wizard up to step 6 work; step 7 + the inventory pass
# degrade with the existing AI-outage message). Path overridable via
# POLICYCODEX_CONFIG_PATH for tests and local dev.
SECRETS_FILE="${POLICYCODEX_CONFIG_PATH:-/secrets/config.env}"
if [ -f "$SECRETS_FILE" ]; then
    set -a
    . "$SECRETS_FILE"
    set +a
fi
