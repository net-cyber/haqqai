# PROJECT KNOWLEDGE BASE

This file provides guidance to AI agents when working with code in this repository.

## KEY NOTES

- Python deps live in a `uv`-managed virtualenv at `.venv` (repo root). If it doesn't exist yet, create it
  with `uv sync --frozen`, then `source .venv/bin/activate`.
- Test secrets (API keys etc.) are resolved by `backend/tests/utils/aws_secrets.py`, in order: process
  env vars → the gitignored `.vscode/.env` (also used by the pytest commands in `backend/AGENTS.md`;
  create it by copying `.vscode/env_template.txt`) → AWS Secrets Manager (requires `aws sso login`).
  Tests declare what they need via `@pytest.mark.secrets(TestSecret.X)`. If a key you need still can't
  be resolved, ask the user rather than skipping tests.
- If using `playwright` to explore the frontend, log in with username `admin_user@example.com` and password
  `TestPassword123!` (the admin user created by the playwright global setup — see
  `web/tests/e2e/constants.ts`). If it doesn't exist yet, register it via the signup page; the first user
  registered automatically becomes admin. The app can be accessed at `http://localhost:3000`.
- You should assume that all Onyx services are running. To verify, you can check the `backend/log` directory to
  make sure we see logs coming out from the relevant service.
- To connect to the Postgres database, use:
  `PGPASSWORD="${POSTGRES_PASSWORD:-password}" psql -h "${POSTGRES_HOST:-localhost}" -U postgres -c "<SQL>"`.
  This works on a host checkout and inside the devcontainer. If no `psql` client is available, fall back to
  `docker exec onyx-relational_db-1 psql -U postgres -c "<SQL>"` (no `-it` — agent shells have no TTY).
- When making calls to the backend, always go through the frontend. E.g. make a call to `http://localhost:3000/api/persona` not `http://localhost:8080/api/persona`
- If `.agents-local.md` exists at the repo root and its rules are not already in your context,
  read and follow it. It carries developer-local agent guidance and is never committed.

## Docker Development Setup

For complete Docker development commands and troubleshooting, see:
**[deployment/docker_compose/DOCKER_COMMANDS.md](deployment/docker_compose/DOCKER_COMMANDS.md)**

### Quick Start for Local Development with Hot-Reload

```bash
cd deployment/docker_compose

# First time - builds images and starts with hot-reload
docker compose \
  -f docker-compose.yml \
  -f docker-compose.dev.yml \
  -f docker-compose.hotreload.yml \
  up -d --build

# Subsequent starts (no rebuild needed)
docker compose \
  -f docker-compose.yml \
  -f docker-compose.dev.yml \
  -f docker-compose.hotreload.yml \
  up -d

# Check status
docker compose -f docker-compose.yml -f docker-compose.dev.yml -f docker-compose.hotreload.yml ps

# View logs
docker compose -f docker-compose.yml -f docker-compose.dev.yml -f docker-compose.hotreload.yml logs -f
```

### Access Points (Local Development)
- **Frontend**: http://localhost:3000 (with hot-reload)
- **Backend API**: http://localhost:8080 (with hot-reload via uvicorn --reload)
- **PostgreSQL**: localhost:5434 (mapped from container's 5432)
- **Redis**: localhost:6379
- **OpenSearch**: localhost:9200
- **MinIO**: localhost:9004 (API), localhost:9005 (Console)

**Note:** Nginx is not needed for local development. Access services directly via their ports.

## Project Overview

**Onyx** (formerly Danswer) is an open-source Gen-AI and Enterprise Search platform that connects to company documents, apps, and people. It features a modular architecture with both Community Edition (MIT licensed) and Enterprise Edition offerings.

### Technology Stack

- **Backend**: Python 3.13, FastAPI, SQLAlchemy, Alembic, Celery
- **Frontend**: Next.js 16, React 19, TypeScript, Tailwind CSS
- **Database**: PostgreSQL with Redis caching
- **Search**: OpenSearch-backed keyword and vector document index
- **Auth**: OAuth2, SAML, multi-provider support
- **AI/ML**: LangChain, LiteLLM, multiple embedding models

### Repository Layout & Sub-project Guides

Each sub-project has its own agents file with the standards for that area — read it before working
there:

- `backend/` — FastAPI app + Celery workers. `onyx/` is the Community Edition core, `ee/` mirrors its
  layout for Enterprise features, `alembic/` holds migrations, `tests/` the test suites. Standards
  (Celery, migrations, testing, error handling, LLM tracing): `backend/AGENTS.md`.
- `web/` — Next.js frontend. Standards (also cover `desktop/`, the Tauri shell): `web/AGENTS.md`.
- `mobile/` — React Native + Expo app. Standards: `mobile/AGENTS.md`. Mobile differs from web on
  several points (no DOM, NativeWind, expo-router), so do **not** assume the web rules apply there.

Explore the tree with `ls` rather than relying on docs for the full package list.

## Code Quality

```bash
# Install and run pre-commit hooks
pre-commit install
pre-commit run --all-files

# Faster: run only on the files you touched
pre-commit run --files <path> [<path> ...]
```

NOTE: Always make sure everything is strictly typed (both in Python and Typescript).

NOTE: Keep code comments brief and focused on information that stays relevant long-term.

## Writing

These rules apply to all prose you write: docs, commit messages, PR descriptions, reports, and replies.

Follow ASD-STE100 Simplified Technical English for technical text:

- Use approved words only. Each word has one meaning.
- Use one word for one idea. Do not use two words for the same thing.
- Write short sentences. Use 20 words or less for instructions.
- Use active voice. Write "Turn the switch", not "The switch must be turned".
- Write short paragraphs. Keep one topic in each paragraph.
- Keep code comments focused on information that is relevant long-term or for future readers.

## Testing

There are 4 main types of tests: unit, external dependency unit, integration, and playwright e2e
(`web/tests/e2e`). Commands and guidance for all four live in `backend/AGENTS.md`; shared fixtures
and deeper detail in `backend/tests/README.md`. Prefer integration tests over the other types.

## Logs

When (1) writing integration tests or (2) doing live tests (e.g. curl / playwright) you can get access
to logs via the `backend/log/<service_name>_debug.log` file. All Onyx services (api_server, web_server, celery_X)
will be tailing their logs to this file.

## Security Considerations

- Never commit API keys or secrets to the repository
- Use the encrypted credential storage for connector credentials
- Follow existing RBAC patterns for new features

## Creating a Plan

When creating a plan in the `plans` directory (gitignored — create it if it doesn't exist), make sure to
include at least these elements:

**Issues to Address**
What the change is meant to do.

**Important Notes**
Things you come across in your research that are important to the implementation.

**Implementation strategy**
How you are going to make the changes happen. High level approach.

**Tests**
What unit (use rarely), external dependency unit, integration, and playwright tests you plan to write to
verify the correct behavior. Don't overtest. Usually, a given change only needs one type of test.

Do NOT include these: _Timeline_, _Rollback plan_

This is a minimal list - feel free to include more. Do NOT write code as part of your plan.
Keep it high level. You can reference certain files or functions though.

Before writing your plan, make sure to do research. Explore the relevant sections in the codebase.

## Best Practices

In addition to the other content in this file, best practices for contributing
to the codebase can be found in the "Engineering Best Practices" section of
`CONTRIBUTING.md`. Understand its contents and follow them.


Haqqai Platform — Operations & Technical Runbook 
Table of Contents 
Oracle Cloud Infrastructure
SSH Access
Docker & Container Management
Checking for Errors
Environment Configuration
Networking & Firewall
CI/CD Pipeline
Backups
Common Problems & Fixes
Useful Commands Cheatsheet 
Oracle Cloud Infrastructure 
Account DetailsField ValueAccount email natiseyoum367@gmail.comTenancy natiseyoum367Home region Canada Southeast (Toronto) — ca-toronto-1Console URL https://cloud.oracle.com 
Instance DetailsField ValueInstance name instance-20260607-0052Shape VM.Standard.A1.Flex (ARM64 Ampere)OCPU 4RAM 24 GBBoot volume 100 GB SSDOS Ubuntu 24.04 LTS aarch64Public IP 129.153.56.175Private IP 10.0.0.116Availability domain AD-1 (BxcR:CA-TORONTO-1-AD-1)Fault domain FD-2Launched Jun 07, 2026 04:52 UTC 
Account Type 
Pay As You Go (upgraded from Free Trial)
ARM compute (4 OCPU, 24 GB RAM) → Always Free = $0/month
Boot volume (100 GB) → ~$5/month
No other charges as long as you stay within Always Free limits 
How to Access Oracle Console 
Go to https://cloud.oracle.com
Sign in with natiseyoum367@gmail.com
Make sure region shows Canada Southeast (Toronto) top right 
How to Find Your Instance 
Menu (☰) → Compute → Instances → click instance-20260607-0052 
How to Check Instance Status 
On instance page, status should show Running (green)
If it shows Stopped, click Start button top rightHow to Start/Stop/Reboot Instance 
Go to instance page
Click Actions button → choose Start / Stop / Reboot 
Networking ResourcesResource NameVCN vcn-20260607-0130Subnet subnet-20260607-0130Internet Gateway Internet Gateway vcn-20260607-0130Security List Default Security List for vcn-20260607-0130 
How to Add/Edit Firewall Rules (Oracle Side) 
Menu → Networking → Virtual Cloud Networks
Click vcn-20260607-0130
Click subnet-20260607-0130
Click Security tab
Click Default Security List for vcn-20260607-0130
Click Security rules tab
Click Add Ingress Rules 
SSH Access 
Prerequisites 
Private key file: ssh-key-2026-06-06.key (saved in ~/Downloads)
Username: ubuntu
Host: 129.153.56.175 
Connect to Server 
# Fix key permissions (only needed once)
chmod 400 ~/Downloads/ssh-key-2026-06-06.key
# Connect
ssh -i ~/Downloads/ssh-key-2026-06-06.key -o IdentitiesOnly=yes ubuntu@129.153.56.175

If SSH Fails 
# Test if server is reachable
ping 129.153.56.175
# Test if SSH port is open
nc -zv 129.153.56.175 22
# Try with verbose output to see what's failing
ssh -v -i ~/Downloads/ssh-key-2026-06-06.key -o IdentitiesOnly=yes ubuntu@129.153.56.175

Common SSH ErrorsError Cause FixPermission denied (publickey) Wrong key or permissions Run chmod 400 on key fileToo many authentication failures SSH agent trying multiple keys Add -o IdentitiesOnly=yesConnection refused Server stopped or firewall Check Oracle console, verify port 22 ingress ruleConnection timed out Network issue or server down Check Oracle console instance status 
Docker & Container Management 
Application Directorycd /home/ubuntu/haqqai/deployment/docker_compose

Check All Container Status 
docker compose ps

Expected output — all containers should show Up or healthy: NAME STATUS onyx-api_server-1 Up (healthy) onyx
background-1 Up onyx-cache-1 Up onyx-code-interpreter-1 Up onyx-indexing_model_server-1 Up
(healthy) onyx-inference_model_server-1 Up (healthy) onyx-minio-1 Up (healthy) onyx-nginx-1 Up
(healthy) onyx-opensearch-1 Up onyx-relational_db-1 Up (healthy) onyx-web_server-1 Up 
Start All Containers 
docker compose up -d

Stop All Containers 
docker compose down

Restart All Containers 
docker compose restart

Restart Specific Container 
docker compose restart api_server
docker compose restart web_server
docker compose restart nginx

Force Recreate (use after .env changes) 
# All containers
docker compose up -d --force-recreate
# Specific container
docker compose up -d --force-recreate api_server

Pull Latest Images 
docker compose pull

Check Container Resource Usage 
docker stats --no-stream

Check Disk Usage 
df -h
docker system df

Checking for Errors 
Check Logs for a Specific Container 
# Last 50 lines
docker compose logs api_server --tail=50
# Follow live logsdocker compose logs -f api_server
# All containers at once
docker compose logs --tail=20

Container-Specific Log Commands 
# Frontend (Next.js)
docker compose logs web_server --tail=50
# Backend API
docker compose logs api_server --tail=50
# Nginx (connection/routing issues)
docker compose logs nginx --tail=50
# Background workers (indexing issues)
docker compose logs background --tail=50
# OpenSearch (search issues)
docker compose logs opensearch --tail=50
# Database
docker compose logs relational_db --tail=50
# Embedding models
docker compose logs indexing_model_server --tail=50
docker compose logs inference_model_server --tail=50

Check Container Health Details 
# Get detailed health check info for a container
docker inspect --format='{{json .State.Health}}' onyx-api_server-1 | python3 -m json.tool
# Check all unhealthy containers
docker ps --filter health=unhealthy

Check What Ports Are Exposed 
docker compose ps --format "table {{.Name}}\t{{.Ports}}"

Check if Application is Responding 
# Check nginx (port 80)
curl -I http://localhost
# Check API server directly
curl http://localhost:8080/health
# Check web server directly
curl http://localhost:3000

Check Server System Logs 
# System errors
sudo journalctl -xe --no-pager | tail -50
# Docker daemon logs
sudo journalctl -u docker --no-pager | tail -50

Check Memory Usage 
free -h
Check CPU Usage 
top
# or
htop

Check Disk Usage 
df -h /
du -sh /home/ubuntu/haqqai/

Check Network Connections 
ss -tlnp

Environment Configuration 
.env File Location 
/home/ubuntu/haqqai/deployment/docker_compose/.env

View Current .env 
cat /home/ubuntu/haqqai/deployment/docker_compose/.env

Key Variables 
# Enterprise features (must be set for white-labeling etc)
ENABLE_PAID_ENTERPRISE_EDITION_FEATURES=true
LICENSE_ENFORCEMENT_ENABLED=false
# Domain
DOMAIN=haqqai.lambadinaai.com
# LLM Configuration (add your API key here)
GEN_AI_API_KEY=your-anthropic-or-openai-key
# Authentication
AUTH_TYPE=basic
# Instance branding
ENV_SEED_CONFIGURATION={"seeded_name": "Haqqai", "admin_user_emails": ["youremail@gmail.com"]}

Edit .env 
nano /home/ubuntu/haqqai/deployment/docker_compose/.env

Apply .env Changes 
cd /home/ubuntu/haqqai/deployment/docker_compose
docker compose up -d --force-recreate

Important: docker compose restart does NOT reload env variables. Always use --force-recreate after editing .env. 
Networking & FirewallUbuntu Firewall (iptables) 
Check current rules: bash sudo iptables -L INPUT -n --line-numbers 
Add a port: bash sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport PORT_NUMBER -j ACCEPT
sudo netfilter-persistent save 
Remove a rule: bash sudo iptables -D INPUT LINE_NUMBER sudo netfilter-persistent save 
Current Open PortsPort Purpose22 SSH80 HTTP (nginx)443 HTTPS (nginx)3000 Web server direct access 
DNS Configuration 
Registrar: Namecheap
Domain: lambadinaai.com
Subdomain: haqqai.lambadinaai.com → A Record → 129.153.56.175
DNS propagation can take up to 30 minutes after changes 
Check DNS Propagation 
# From your local machine
nslookup haqqai.lambadinaai.com
# Or
dig haqqai.lambadinaai.com

CI/CD Pipeline 
How It Works 
Push code to ft/change branch on GitHub
GitHub Actions automatically triggers
Job 1 (build-and-push): Builds ARM64 Docker images and pushes to Docker Hub
Job 2 (deploy): SSHs into Oracle server and deploys new images 
Monitor CI/CD 
Go to https://github.com/net-cyber/haqqai/actions
Click the latest workflow run
Click on each job to see logs 
Re-run a Failed Deployment 
Go to https://github.com/net-cyber/haqqai/actions
Click the failed run
Click Re-run failed jobs 
Manual Deployment (without pushing code) 
SSH into server and run: bash cd /home/ubuntu/haqqai/deployment/docker_compose docker compose pull docker
compose up -d --force-recreate docker image prune -f 
GitHub Secrets (if you need to update them) 
Go to: https://github.com/net-cyber/haqqai/settings/secrets/actionsSecret PurposeDOCKER_USERNAME Docker Hub loginDOCKER_PASSWORD Docker Hub access tokenORACLE_SSH_KEYORACLE_HOSTORACLE_USERServer IP (129.153.56.175)Server username (ubuntu)
Docker Hub Images 
https://hub.docker.com/r/devnatnaels/haqqai-backend
https://hub.docker.com/r/devnatnaels/haqqai-web 
Backups 
What Needs Backing UpData Location ImportancePostgreSQL database Docker volume onyx_db_data 🔴 CriticalOpenSearch index Docker volume onyx_opensearch_data 🟡 HighMinIO files Docker volume onyx_minio_data 🟡 High.env file /home/ubuntu/haqqai/deployment/docker_compose/.env 🔴 CriticalSSH private key ~/Downloads/ssh-key-2026-06-06.key (local) 🔴 Critical 
Backup PostgreSQL Database 
docker compose exec relational_db pg_dump -U postgres onyx > backup_$(date +%Y%m%d).sql

Restore PostgreSQL Database 
cat backup_20260607.sql | docker compose exec -T relational_db psql -U postgres onyx

List Docker Volumes 
docker volume ls | grep onyx

Common Problems & Fixes 
Problem: Site not loading (ERR_CONNECTION_REFUSED) 
# Check if nginx is running
docker compose ps nginx
# If not running, start it
docker compose up -d nginx
# Check nginx logs
docker compose logs nginx --tail=30

Problem: Site loads but shows error page 
# Check api_server logs
docker compose logs api_server --tail=50
# Check if api_server is healthy
docker compose ps api_server

Problem: Document indexing not working 
# Check background worker
docker compose logs background --tail=50
Private key to SSH into server# Check model servers
docker compose logs indexing_model_server --tail=30

Problem: Slow search results 
# Check OpenSearch health
curl http://localhost:9200/_cluster/health
# Check memory usage
docker stats onyx-opensearch-1 --no-stream

Problem: Out of disk space 
# Check disk usage
df -h
# Clean up old Docker images
docker image prune -a
# Clean up unused volumes
docker volume prune
# Check what's taking space
du -sh /var/lib/docker/

Problem: Out of memory (containers crashing) 
# Check memory
free -h
docker stats --no-stream
# Reduce OpenSearch heap (edit .env)
# Add: OPENSEARCH_JAVA_OPTS=-Xms2g -Xmx2g
# Then force recreate opensearch
docker compose up -d --force-recreate opensearch

Problem: Container keeps restarting 
# Check restart count and last error
docker inspect onyx-api_server-1 | grep -A 5 "RestartCount"
# Check logs for crash reason
docker compose logs api_server --tail=100

Problem: Changes not showing after deployment 
# Force recreate all containers
docker compose up -d --force-recreate
# Hard refresh browser (Ctrl+Shift+R)

Problem: Can’t SSH into server 
Check Oracle console — is instance Running?
Check Security List — is port 22 open for 0.0.0.0/0?
Check key permissions: chmod 400 ~/Downloads/ssh-key-2026-06-06.key
Try: ssh -v for verbose output 
Useful Commands CheatsheetQuick Health Check 
cd /home/ubuntu/haqqai/deployment/docker_compose && docker compose ps

Watch Live Logs (all containers) 
cd /home/ubuntu/haqqai/deployment/docker_compose && docker compose logs -f

Full Restart 
cd /home/ubuntu/haqqai/deployment/docker_compose
docker compose down
docker compose up -d

Check RAM 
free -h && docker stats --no-stream

Check Disk 
df -h && docker system df

Update .env and Apply 
nano /home/ubuntu/haqqai/deployment/docker_compose/.env
# Make your changes, save with Ctrl+X
docker compose up -d --force-recreate

Backup Database 
cd /home/ubuntu/haqqai/deployment/docker_compose
docker compose exec relational_db pg_dump -U postgres onyx > ~/backup_$(date +%Y%m%d_%H%M).sql
echo "Backup saved to ~/backup_$(date +%Y%m%d_%H%M).sql"

Check Application URL 
curl -I http://haqqai.lambadinaai.com
curl -I http://129.153.56.175

Get Container Shell (for debugging) 
# Enter api_server container
docker compose exec api_server bash
# Enter web_server container
docker compose exec web_server sh
# Enter database
docker compose exec relational_db psql -U postgres onyx