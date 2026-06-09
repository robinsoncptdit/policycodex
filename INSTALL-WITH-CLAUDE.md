# Install PolicyCodex with Claude Code

This is a **copy-and-paste prompt**. You do not need to understand Docker, Django, or the command line. Claude Code will do the work and explain each step as it goes.

**How to use it:**

1. Install Claude Code (https://claude.com/claude-code) on the computer you will be working from (your laptop is fine, even if PolicyCodex itself will run on a server somewhere else).
2. Open Claude Code in a terminal.
3. Copy **everything below the line** (the whole block) and paste it in as your first message.
4. Answer Claude's questions as they come. It will pause and ask before doing anything that changes your system.

Claude will walk you from an empty machine all the way to a running PolicyCodex you can log in to.

---

You are helping me, a non-technical diocesan IT administrator, install and run **PolicyCodex** for the first time. PolicyCodex is an open-source, self-hosted Django application that ships as a Docker container. I may know very little about servers, Docker, or Git. Be patient, explain what each step does in one plain sentence before you run it, and **always pause and ask for my confirmation before any action that installs software, changes my system, opens a network port, or could expose the app to the internet.** Never paste my secrets (API keys, private keys, passwords) into your chat output.

Work through the following phases in order. Do not skip ahead. At the start of each phase, tell me in one sentence what we are about to do and why.

## Phase 0 — Where will PolicyCodex run?

Ask me one question first: **do I want to run PolicyCodex on a remote server (a "VM" — recommended for a real diocese) or on this local computer (fine for trying it out)?**

- **If local:** everything happens on this machine. Skip Phase 1 and continue at Phase 2, using `localhost` as the host throughout.
- **If remote VM:** continue to Phase 1 to connect to it. From then on, run the install commands *on the VM* (over SSH), not on my laptop.

If I am not sure, recommend a small cloud VM (for example a 2 vCPU / 4 GB Ubuntu 22.04 LTS instance from any provider) and explain in two sentences that a server keeps PolicyCodex running when my laptop is off, which is what a diocese wants.

## Phase 1 — Connect to the VM (remote only)

1. Ask me for the VM's address and login: its IP address or hostname, the SSH username (often `ubuntu`, `root`, or a name my cloud provider gave me), and whether I have an SSH key file or a password.
2. If I have a key file, help me connect with `ssh -i <path-to-key> <user>@<host>`. If I have never used SSH, explain in one sentence that it is a secure remote login.
3. If the connection fails, help me diagnose the common causes (wrong path to the key, key file permissions too open — fix with `chmod 600`, security-group/firewall blocking port 22, wrong username) one at a time. Do not retry the same failing command more than twice without changing something.
4. Once connected, confirm the operating system with `cat /etc/os-release` so you choose the right install commands later.

**Stop and confirm** I am logged into the VM before continuing.

## Phase 2 — Make sure Docker is installed

PolicyCodex needs Docker Engine and the Docker Compose v2 plugin.

1. Check what is already there: run `docker --version` and `docker compose version`. If both succeed, tell me Docker is ready and skip to Phase 3.
2. If Docker is missing, install it for my detected OS. Tell me the exact commands first and wait for my OK. For Debian/Ubuntu, the official convenience path is:
   ```bash
   curl -fsSL https://get.docker.com -o get-docker.sh
   sh get-docker.sh
   ```
   For other systems, point me to https://docs.docker.com/get-docker/ and adapt.
3. So I can run Docker without `sudo`, offer to add my user to the `docker` group (`sudo usermod -aG docker $USER`) and explain I must log out and back in (or run `newgrp docker`) for it to take effect. Confirm with `docker run --rm hello-world`.
4. Re-confirm `docker compose version` reports v2 (it should look like `Docker Compose version v2.x`). PolicyCodex requires Compose **v2**, not the old `docker-compose` script.

## Phase 3 — Get the PolicyCodex code

1. Make sure `git` is installed (`git --version`; install it if missing).
2. Ask me whether I have my own fork/copy of the PolicyCodex repository or should use the public one. Clone it into my home directory:
   ```bash
   git clone https://github.com/<org>/policycodex.git
   cd policycodex
   ```
   Use the public repo URL if I do not have my own. After cloning, `cd policycodex` — every command after this runs from the repo root.
3. Briefly read `README.md` and `HOWTO-GitHub-Team-Setup.md` in this repo so your later guidance matches the current code. Do not just rely on this prompt for details that those files cover.

## Phase 4 — Configure the instance (`.env`)

PolicyCodex reads its non-secret settings from a file called `.env`.

1. Create it from the template: `cp .env.example .env`. Then open `.env` and walk me through filling it in. The keys that matter:
   - **`DJANGO_SECRET_KEY`** — required. Generate a strong one for me and put it in (this generator deliberately avoids the `$` character, which Docker Compose would otherwise treat specially):
     ```bash
     python3 -c "import secrets,string; a=string.ascii_letters+string.digits+'!@%^&*(-_=+)'; print(''.join(secrets.choice(a) for _ in range(50)))"
     ```
   - **`DJANGO_DEBUG`** — leave empty (off) for a real install. Only set `1` for local debugging.
   - **`DJANGO_ALLOWED_HOSTS`** — the hostnames/IPs this instance answers on. For local use, `localhost,127.0.0.1` is fine. For a VM, add the VM's public hostname or IP (e.g. `policycodex.example.org,203.0.113.10`). If this is wrong, the site returns a "Bad Request (400)".
   - **`DJANGO_SUPERUSER_USERNAME` / `DJANGO_SUPERUSER_EMAIL` / `DJANGO_SUPERUSER_PASSWORD`** — set all three. When all three are present, the container **creates my admin login automatically on first start**, which is the account I will use to reach onboarding. Pick a strong password. (If I would rather not put a password in the file, leave these blank and we will create the admin in Phase 7 instead.)
   - Leave `POLICYCODEX_DB_PATH`, `POLICYCODEX_WORKING_COPY_ROOT`, and `POLICYCODEX_CONFIG_PATH` at their defaults (`/data/...` and `/secrets/config.env`) — those point at the persistent volume and the read-only credentials mount and should not change.
   - `POLICYCODEX_POLICY_REPO_URL` and `POLICYCODEX_POLICY_BRANCH` may be left blank; the onboarding wizard sets the policy repo.
2. **Secrets never go in `.env`.** Remind me of that. The GitHub App private key and my LLM API key live in the credentials directory in the next phase.

## Phase 5 — Set up credentials (read-only, never committed)

PolicyCodex mounts a host directory `~/.config/policycodex/` read-only into the container at `/secrets`. That is where real secrets live so they never enter the image or any file in Git.

1. Create it: `mkdir -p ~/.config/policycodex`.
2. Create `~/.config/policycodex/config.env`. This is where the GitHub App credentials AND the LLM API key go. Tell me which values it needs by reading `HOWTO-GitHub-Team-Setup.md` and `app/git_provider/github_config.py` in the repo (so you give me the current, exact key names rather than guessing). At minimum it includes:
   - `POLICYCODEX_GH_PRIVATE_KEY_PATH`, pointing at a path **inside** `/secrets/` (for example `/secrets/github-app-private-key.pem`), because the host file at `~/.config/policycodex/github-app-private-key.pem` appears at `/secrets/...` inside the container.
   - The LLM API key for the provider I picked in the wizard's step 6, using that provider's native env-name convention: `ANTHROPIC_API_KEY=sk-ant-…` for Claude (the v0.1 default), `OPENAI_API_KEY=…` for OpenAI, `GOOGLE_API_KEY=…` for Gemini, `AZURE_OPENAI_API_KEY=…` for Azure. The container sources `/secrets/config.env` at startup via `docker/load-secrets.sh`, so every line in this file becomes a process env var the SDK reads directly — no per-provider Python wiring needed.

   Format: POSIX `KEY=VALUE` per line, `#` for comments, quotes optional. A malformed line is logged but does not block boot; well-formed lines up to it still get exported.
3. **I must do the GitHub App creation steps myself in a browser** (creating the App, installing it on my org, downloading its private key). Walk me through `HOWTO-GitHub-Team-Setup.md` for that, and tell me where to save the downloaded `.pem` file (into `~/.config/policycodex/`). Do not ask me to paste the key into this chat — just confirm the file is in place with `ls -l ~/.config/policycodex/` (filenames only).
4. If I only want to *try* PolicyCodex and am not ready to connect a real GitHub org yet, tell me I can still start the app and explore the UI, and come back to the GitHub App setup before running the onboarding wizard's repo step.

## Phase 6 — Point PolicyCodex at my existing policy files

There are two ways my existing policy documents reach PolicyCodex; explain both and let me pick:

- **Through the browser (simplest, used during onboarding):** the onboarding wizard's final step lets me upload my Document Retention Policy (and other reference documents) directly. Most first-time installs use only this. No directory setup needed.
- **As a folder for the bulk AI inventory pass:** if I already have a folder full of existing policy PDFs/DOCX/MD/TXT files I want PolicyCodex to inventory, put that folder where the container can read it. The credentials mount is the clean place: create `~/.config/policycodex/corpus/` on the host and copy my documents in. Inside the container they appear under `/secrets/corpus/`. Later I can run the inventory pass against that path with:
  ```bash
  docker compose exec app python manage.py run_inventory_pass /secrets/corpus
  ```
  Confirm the exact command and arguments against `core/management/commands/run_inventory_pass.py` in the repo before running it, since the inventory pass is the part of the tool that changes most.

For a first install, it is fine to skip the bulk folder and just use the browser upload during onboarding.

## Phase 7 — Build and start the container

1. From the repo root, run the one-command installer: `./install.sh`. Explain it checks Docker, makes sure `.env` exists with a real secret key, then builds the image and starts the stack in the background (`docker compose up --build -d`). The first build downloads the base image and dependencies and can take several minutes — that is normal.
   - If `install.sh` exits early telling me `.env` was just created, that means I am on a fresh checkout; finish Phase 4 (fill in `.env`) and run it again.
   - If it complains `DJANGO_SECRET_KEY` is empty, go back and set it.
2. If I would rather not use the script, the equivalent is `docker compose up --build -d`.
3. Watch it come up: `docker compose logs -f` (Ctrl-C stops watching the logs but leaves the app running). You should see database migrations apply and then `gunicorn` start listening on port 8000.
4. If all three superuser env vars were set, the logs will also show the admin account being created.
5. **Verify it is healthy** without a browser: `curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8000/health/` should print `200`. If it does not, read the logs (`docker compose logs --tail=50`) and help me fix the cause before moving on (common ones: empty/!invalid `DJANGO_SECRET_KEY`, a hostname missing from `DJANGO_ALLOWED_HOSTS`, or the credentials file not in place).

## Phase 8 — Reach the app in a browser

Figure out the right address:

- **Local install:** the address is `http://localhost:8000`.
- **VM install:** for a safe first run, recommend an **SSH tunnel** instead of exposing the port to the internet. From my *laptop*, run `ssh -L 8000:localhost:8000 <user>@<host>`, then open `http://localhost:8000` on my laptop — traffic is encrypted and the app is not publicly exposed. Explain this in one sentence.
  - If I would rather expose it directly, warn me first: I must open port 8000 in the VM's firewall/security group, add the VM's hostname/IP to `DJANGO_ALLOWED_HOSTS`, and understand the app would then be reachable over plain HTTP. For real production, recommend putting it behind a reverse proxy with HTTPS (and point to `HOWTO-GitHub-Team-Setup.md` for the public-handbook subdomain, which is a separate concern). Do not open a public port without my explicit say-so.

Now the **login-then-onboard** flow (this order matters — the catalog and the onboarding wizard both require a login):

1. Send me to **`http://localhost:8000/login/`** and have me sign in with the admin username and password from Phase 4 (or the one we create below).
   - If I did not set the `DJANGO_SUPERUSER_*` values, create the admin now: `docker compose exec app python manage.py createsuperuser` and walk me through the prompts.
2. After logging in, send me to **`http://localhost:8000/onboarding/`** to run the **seven-screen onboarding wizard**: (1) connect or create the private GitHub policy repo, (2) address scheme, (3) versioning, (4) reviewer roles, (5) retention defaults, (6) LLM provider + API key, (7) upload source-of-truth reference documents (the Document Retention Policy is the key one). Read the wizard screens with me and explain each in a sentence. The wizard opens a configuration pull request and then shows a completion screen telling me how to merge it and publish the handbook.
3. **Optional — let Claude drive the wizard for me.** If the `claude-in-chrome` browser tools are available and connected in this session, offer to open the browser and complete the onboarding wizard *with me watching*, filling each screen as I provide the values. **Do not type my LLM API key or any secret into a field on my behalf** — pause and let me enter secrets myself. If the browser tools are not connected, just give me the URLs and guide me click-by-click in plain language; this is expected and fine.
4. When onboarding is done, my home base for running PolicyCodex is the **catalog** at `http://localhost:8000/catalog/`, and I sign in any time at `http://localhost:8000/login/`. Tell me that.

## Phase 9 — Wrap up and hand off

1. Summarize what is now running, where my data lives (the `policycodex-data` Docker volume — it survives restarts), and where my secrets live (`~/.config/policycodex/`, never in Git).
2. Give me the everyday commands in plain terms:
   - See logs: `docker compose logs -f`
   - Stop: `docker compose down` (my data persists in the volume)
   - Start again: `docker compose up -d`
   - Update to a newer PolicyCodex: `git pull` then `./install.sh` (rebuilds; the volume keeps my data)
3. Remind me to keep my admin password and the `.env` file private, and that for a public production deployment I should put the app behind HTTPS.

Throughout: prefer reading the actual files in this repo (`README.md`, `HOWTO-GitHub-Team-Setup.md`, `install.sh`, `.env.example`, `docker-compose.yml`, `docker/entrypoint.sh`) over assuming, because the install path can change between releases. If something this prompt says does not match what you find in those files, trust the files and tell me about the difference.

---

## For maintainers (not part of the pasted prompt)

This prompt mirrors the live Docker install path. **Update it in the same change whenever any of these moves:** `Dockerfile`, `docker-compose.yml`, `docker-compose.pull.yml`, `docker/entrypoint.sh`, `docker/load-secrets.sh`, `install.sh`, `.env.example`, the credentials convention (`~/.config/policycodex/`, `POLICYCODEX_CONFIG_PATH`, `app/git_provider/github_config.py`), the onboarding/login URL routing (`policycodex_site/urls.py`, `core/urls.py`, `app/onboarding/urls.py`), or the inventory-pass command (`core/management/commands/run_inventory_pass.py`). A lockstep guard, `tests/test_install_prompt_sync.py`, fails the suite if this prompt is left pointing at a file, env key, install command, or URL route that no longer exists — so drift in the tracked files trips a red test, not just a stale doc. It cannot check that the prose is *accurate*; a human still reviews wording. Verified against the codebase 2026-06-09 (Python 3.14 / Django 6.0, REPO-05 + REPO-11 + REPO-15 + REPO-17).
