# Scovra deployment

This document tells how Scovra is built, deployed and operated on one Docker
host. Scovra is "the AI operating system for nonprofit funding and reporting".
It runs on the Onyx Docker Compose stack, with Scovra images and one Scovra
overlay file.

## What runs where

### GitHub Actions

The workflow `.github/workflows/deploy.yml` ("Build and Deploy Scovra") starts
on each push to `ft/scovra`. You can also start it manually: **Actions > Build
and Deploy Scovra > Run workflow**. It does these steps:

1. Two jobs build the images in parallel on native arm64 runners
   (`ubuntu-24.04-arm`, no emulation). They push these images to Docker Hub with
   the tags `latest` and the commit SHA:
   - `devnatnaels/scovra-backend` (the `runtime` stage of `backend/Dockerfile`)
   - `devnatnaels/scovra-web`
2. The deploy job copies `deployment/docker_compose/` and `deployment/data/` to
   `/home/ubuntu/scovra/deployment/` on the server.
3. The deploy job connects with SSH and runs a script that:
   - stops with an error if `.env` or `.env.nginx` is missing,
   - stops with an error if `USER_AUTH_SECRET` or `POSTGRES_PASSWORD` is empty
     in `.env`,
   - stops with an error if the Craft network or volume is missing,
   - checks the merged Compose configuration,
   - pulls the images, recreates the containers and removes old images.

The workflow uses these repository secrets (**Settings > Secrets and variables >
Actions**):

| Secret            | Value                                         |
| ----------------- | --------------------------------------------- |
| `DOCKER_USERNAME` | Docker Hub user that owns the images          |
| `DOCKER_PASSWORD` | Docker Hub access token with write permission |
| `ORACLE_HOST`     | Server IP address or host name                |
| `ORACLE_USER`     | SSH user on the server (`ubuntu`)             |
| `ORACLE_SSH_KEY`  | Private SSH key for that user                 |

When you merge a new upstream Onyx release into `ft/scovra`, also change
`SCOVRA_VERSION` in the workflow and `IMAGE_TAG` in the server `.env`.

### Server

The server is one arm64 Linux host with Docker Engine and Docker Compose
v2.24 or later. All Scovra containers are in the Compose project `scovra`.

| Path on the server                                         | Purpose                                     |
| ---------------------------------------------------------- | ------------------------------------------- |
| `/home/ubuntu/scovra/deployment/docker_compose/`           | Compose files. The workflow replaces them.  |
| `/home/ubuntu/scovra/deployment/docker_compose/.env`       | Server settings and secrets. Not in git.    |
| `/home/ubuntu/scovra/deployment/docker_compose/.env.nginx` | `DOMAIN` and `EMAIL` for nginx. Not in git. |
| `/home/ubuntu/scovra/deployment/data/nginx/`               | nginx templates. The workflow replaces them.|
| `/etc/letsencrypt/`                                        | TLS certificates from the host certbot.     |

The deploy uses three Compose files in this sequence:

```bash
docker compose -p scovra \
  -f docker-compose.prod.yml \
  -f docker-compose.craft.yml \
  -f docker-compose.scovra.yml <command>
```

- `docker-compose.prod.yml` is the upstream production stack. It is a generated
  file. Do not edit it.
- `docker-compose.craft.yml` is the upstream Craft overlay (Docker sandboxes).
- `docker-compose.scovra.yml` is the Scovra overlay. It mounts the host
  `/etc/letsencrypt` into nginx (read-only) and keeps the `certbot` container
  stopped, because the host certbot renews the certificates.

| Service                                          | Job                                                                        |
| ------------------------------------------------ | -------------------------------------------------------------------------- |
| `nginx`                                          | HTTP on port 80, HTTPS on port 443. Sends traffic to the app services.     |
| `web_server`                                     | Scovra web app.                                                            |
| `api_server`                                     | API. Runs database migrations at start. Starts Craft sandboxes.            |
| `background`                                     | Celery workers: indexing, scheduled tasks, Craft idle cleanup.             |
| `mcp_server`                                     | Stays idle while `MCP_SERVER_ENABLED=false`.                               |
| `inference_model_server`, `indexing_model_server` | Embedding models (upstream image, tag from `IMAGE_TAG`).                  |
| `relational_db`                                  | Postgres.                                                                  |
| `opensearch`                                     | Search index.                                                              |
| `cache`                                          | Redis.                                                                     |
| `object-store`                                   | File store (SeaweedFS with an S3 API).                                     |
| `object-store-copy`                              | Stays idle. It copies files only from an earlier MinIO store.              |
| `minio`                                          | Does not start (`MINIO_REPLICAS=0`).                                       |
| `code-interpreter`                               | Python tool for chat.                                                      |
| `sandbox-proxy`                                  | Craft egress proxy. It applies the action policies (approvals).            |
| `sandbox-image-prepull`                          | Does not start. It only makes `pull` get the Craft sandbox image.          |
| `certbot`                                        | Does not start. The host certbot renews the certificates.                  |

For each Craft session, `api_server` starts one sandbox container on the Docker
network `onyx_craft_sandbox`. A sandbox can use up to
`SANDBOX_DOCKER_MEMORY_LIMIT` of memory. It stops after
`SANDBOX_IDLE_TIMEOUT_SECONDS` without activity. Make sure that the server has
memory for the sandboxes that run at the same time.

## One-time server prep

Do these steps one time, before the first deploy. Run the commands on the
server.

### 1. Stop the previous stack

The previous stack (Compose project `onyx`) uses ports 80 and 443. Stop it. This
command keeps its containers and volumes, so you can start it again later:

```bash
docker compose -p onyx stop
```

Do not use `down -v`, because it deletes the volumes.

Then look for containers of the previous stack that are still running, for
example old Craft sandboxes:

```bash
docker ps --filter label=com.docker.compose.project=onyx
```

Stop each container that the command shows with `docker stop <name>`.

Do not push to the branch that deploys the previous stack. Its workflow starts
the previous stack again, and both stacks need ports 80 and 443.

### 2. Create the Craft network and volume

`docker-compose.craft.yml` uses them as external resources. If they exist from
an earlier Craft installation, keep them.

```bash
docker network create onyx_craft_sandbox
docker volume create sandbox_proxy_ca
```

### 3. Get the TLS certificate with the host certbot

1. Make a DNS A record for the Scovra host name. Point it to the server IP
   address.
2. Install certbot on the host if it is not installed:

   ```bash
   sudo apt-get update && sudo apt-get install -y certbot
   ```

3. Make sure that no container uses port 80 (step 1). Then get the certificate.
   Use the host name only, with no `https://`:

   ```bash
   sudo certbot certonly --standalone \
     -d app.example.org -m ops@example.org --agree-tos --no-eff-email
   ```

   The certificate must be in `/etc/letsencrypt/live/<DOMAIN>/`. If certbot
   adds a suffix such as `-0001` to the directory name, change `DOMAIN` in
   `.env.nginx` to agree with it.

4. The nginx template includes two TLS files that `certbot certonly` does not
   make. Download them. The URLs use a fixed certbot release, so they do not
   change:

   ```bash
   sudo test -f /etc/letsencrypt/options-ssl-nginx.conf || sudo curl -fsSL \
     -o /etc/letsencrypt/options-ssl-nginx.conf \
     https://raw.githubusercontent.com/certbot/certbot/v5.8.0/certbot/src/certbot/_internal/plugins/nginx/tls_configs/options-ssl-nginx.conf
   sudo test -f /etc/letsencrypt/ssl-dhparams.pem || sudo curl -fsSL \
     -o /etc/letsencrypt/ssl-dhparams.pem \
     https://raw.githubusercontent.com/certbot/certbot/v5.8.0/certbot/src/certbot/ssl-dhparams.pem
   ```

5. Add renewal hooks. A standalone renewal needs port 80, so the hooks stop the
   Scovra nginx container before the renewal and start it again after:

   ```bash
   sudo tee /etc/letsencrypt/renewal-hooks/pre/scovra-nginx-stop.sh >/dev/null <<'EOF'
   #!/bin/sh
   docker stop scovra-nginx-1 || true
   EOF
   sudo tee /etc/letsencrypt/renewal-hooks/post/scovra-nginx-start.sh >/dev/null <<'EOF'
   #!/bin/sh
   docker start scovra-nginx-1 || true
   EOF
   sudo chmod +x /etc/letsencrypt/renewal-hooks/pre/scovra-nginx-stop.sh \
     /etc/letsencrypt/renewal-hooks/post/scovra-nginx-start.sh
   ```

6. Find hooks that stop or start the nginx container of the previous stack (for
   example `onyx-nginx-1`). Remove them, or they start that container again:

   ```bash
   sudo grep -rn "nginx" /etc/letsencrypt/renewal/ /etc/letsencrypt/renewal-hooks/
   ```

7. After the first deploy, test the renewal. The test also runs the hooks:

   ```bash
   sudo certbot renew --dry-run
   ```

### 4. Create `.env` and `.env.nginx`

The workflow copies `env.scovra.template` to the server. On the first run, the
workflow builds the images, copies the files, and then stops because `.env` is
missing. This is the expected result. Then do these steps:

```bash
cd /home/ubuntu/scovra/deployment/docker_compose
cp env.scovra.template .env
chmod 600 .env
nano .env
```

Fill in each blank value. The comments in the file tell what each value does.
Use these commands to make the secrets:

```bash
openssl rand -hex 32   # USER_AUTH_SECRET
openssl rand -hex 24   # POSTGRES_PASSWORD
openssl rand -hex 16   # S3_AWS_ACCESS_KEY_ID (also MINIO_ROOT_USER)
openssl rand -hex 32   # S3_AWS_SECRET_ACCESS_KEY (also MINIO_ROOT_PASSWORD)
```

Then create `.env.nginx` with the host name and an email address:

```bash
printf 'DOMAIN=%s\nEMAIL=%s\n' app.example.org ops@example.org > .env.nginx
chmod 600 .env.nginx
```

Do not set `DEV_MODE` on the server. Do not set `SANDBOX_CONTAINER_IMAGE`:
`IMAGE_TAG` sets the Craft sandbox image and the model server images to the
same upstream release.

### 5. Deploy and check

Run the workflow again (push to `ft/scovra`, or **Run workflow**). Then check
the containers and the API:

```bash
docker compose -p scovra ps
curl -fsS https://app.example.org/api/health
```

## License prerequisite for Craft

Craft (sessions, scheduled tasks, approvals, and Gmail, Google Drive and Google
Calendar actions) needs an **Onyx Business or Enterprise license**. Chat and the
Scovra agents do not need a license.

Apply the license in one of these two ways:

- Go to `/admin/billing` as an admin. A self-hosted Business checkout includes a
  1-month free trial. The checkout needs a payment card.
- Send the signed license file to `POST /api/license/upload` as an admin, in the
  multipart field `license_file`.

Without a license:

- the Craft tab in the sidebar shows an upgrade badge and you cannot open it,
- the `/api/build/*` routes return 403,
- `GET /api/settings` returns `onyx_craft_requires_upgrade: true`.

Do not change or go around the license check. The Onyx Enterprise code has a
commercial license.

## Post-deploy admin checklist

1. Open `https://<DOMAIN>` and create the first account. The first account
   becomes the admin.
2. Add an LLM provider and set the default model at `/admin/language-models`.
3. Add a web search provider at `/admin/web-search`. The Scout agent needs it.
4. Apply the license at `/admin/billing` (see above).
5. At `/admin/plugins`, connect the Google apps: Gmail, Google Drive and Google
   Calendar. Each app needs an OAuth client ("Web application") in Google
   Cloud. Add this authorized redirect URI to the client:
   `https://<DOMAIN>/craft/v1/apps/oauth/callback`. This URI is `WEB_DOMAIN`
   plus `/craft/v1/apps/oauth/callback`. Users connect their own accounts at
   `/craft/v1/plugins`.
6. Set the action policies of each app. In the UI, ALWAYS is "Auto-approve", ASK
   is "Ask" and DENY is "Deny". The Google Drive create and edit actions are
   ASK by default, so set them to ALWAYS explicitly.

   | App             | Actions                                                                                                                                                  | Policy |
   | --------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------- | ------ |
   | Gmail           | Read messages, Read threads, Read attachments, Read drafts, List labels, Read profile                                                                    | ALWAYS |
   | Gmail           | Create a draft, Update a draft                                                                                                                           | ALWAYS |
   | Gmail           | Send a message, Send a draft, Modify message labels                                                                                                      | ASK    |
   | Gmail           | Trash a message, Delete a draft                                                                                                                          | DENY   |
   | Google Drive    | Read files, Export a document, List shared drives, Read a document, Read a spreadsheet, Read a presentation                                              | ALWAYS |
   | Google Drive    | Create or upload a file, Edit a file, Create a document, Edit a document, Create a spreadsheet, Edit a spreadsheet, Create a presentation, Edit a presentation | ALWAYS |
   | Google Drive    | Delete a file                                                                                                                                            | DENY   |
   | Google Calendar | List calendars, Read events, Query free/busy                                                                                                             | ALWAYS |
   | Google Calendar | Create an event, Update an event                                                                                                                         | ASK    |
   | Google Calendar | Delete an event                                                                                                                                          | DENY   |

7. Do not pre-approve Gmail in a scheduled task. A pre-approval covers all ASK
   actions of the app, also "Send a message" and "Send a draft". Without a
   pre-approval, drafts continue (ALWAYS), and a send attempt stops the run
   until a person approves it.

## Operations

Run these commands in `/home/ubuntu/scovra/deployment/docker_compose`. The
`.env` file sets `COMPOSE_PROJECT_NAME=scovra`, but add `-p scovra` to be safe.

```bash
# Show the containers
docker compose -p scovra ps

# Show the logs of one service
docker compose -p scovra logs -f --tail=100 api_server

# Apply a change to .env ("restart" does not read .env again)
docker compose -p scovra -f docker-compose.prod.yml -f docker-compose.craft.yml \
  -f docker-compose.scovra.yml up -d --force-recreate

# Back up the database
docker compose -p scovra exec -T relational_db \
  pg_dump -U postgres postgres > ~/scovra_$(date +%Y%m%d_%H%M).sql
```

Keep a copy of `.env` and `.env.nginx` in a safe place. `.env` holds the
database password, the object store keys and the encryption key.

## Roll back to the previous stack

1. Stop Scovra. This keeps the Scovra containers and volumes (`scovra_*`):

   ```bash
   docker compose -p scovra stop
   ```

2. Start the previous stack again:

   ```bash
   docker compose -p onyx start
   ```

3. Remove the Scovra renewal hooks from `/etc/letsencrypt/renewal-hooks/pre/`
   and `/etc/letsencrypt/renewal-hooks/post/`. Put back the hooks of the
   previous stack, if it had hooks.
4. Do not push to `ft/scovra` while the previous stack runs. A push starts the
   Scovra deploy again, and both stacks need ports 80 and 443.

To go back to an earlier Scovra build instead, set `ONYX_BACKEND_IMAGE` and
`ONYX_WEB_SERVER_IMAGE` in `.env` to the commit SHA tag (for example
`devnatnaels/scovra-backend:<sha>`). Then apply the change to `.env` (see
Operations). An earlier build can fail on a database that a later build
migrated. Restore a database backup in that case. Remove the SHA tags from
`.env` before the next deploy, or the deploy keeps the earlier build.
