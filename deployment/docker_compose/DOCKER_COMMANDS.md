# Docker Development Commands Reference

## Quick Reference

### Current Setup Status
✅ **Development environment with hot-reload is running**
- Frontend (Next.js): http://localhost:3000
- Backend API: http://localhost:8080
- PostgreSQL: localhost:5432 (mapped to 5434 to avoid conflicts)
- Redis: localhost:6379
- OpenSearch: localhost:9200
- MinIO: localhost:9004 (API), localhost:9005 (Console)

⚠️ **Nginx is NOT needed for local development** - Access services directly via their exposed ports above.

---

## Development Workflow Commands

### Starting Development Environment

```bash
# Navigate to docker compose directory
cd /home/analemma/dev/haqqai/deployment/docker_compose

# Start all services with hot-reload (FIRST TIME - builds images)
docker compose \
  -f docker-compose.yml \
  -f docker-compose.dev.yml \
  -f docker-compose.hotreload.yml \
  up -d --build

# Start all services with hot-reload (SUBSEQUENT TIMES - no build needed)
docker compose \
  -f docker-compose.yml \
  -f docker-compose.dev.yml \
  -f docker-compose.hotreload.yml \
  up -d
```

### Checking Status

```bash
# Check all containers status
docker compose -f docker-compose.yml -f docker-compose.dev.yml -f docker-compose.hotreload.yml ps

# Check specific service
docker compose -f docker-compose.yml -f docker-compose.dev.yml -f docker-compose.hotreload.yml ps web_server
docker compose -f docker-compose.yml -f docker-compose.dev.yml -f docker-compose.hotreload.yml ps api_server

# Quick health check - see which are healthy
docker ps --format "table {{.Names}}\t{{.Status}}"
```

### Viewing Logs

```bash
# Follow all logs
docker compose -f docker-compose.yml -f docker-compose.dev.yml -f docker-compose.hotreload.yml logs -f

# Follow specific service logs
docker compose -f docker-compose.yml -f docker-compose.dev.yml -f docker-compose.hotreload.yml logs -f web_server
docker compose -f docker-compose.yml -f docker-compose.dev.yml -f docker-compose.hotreload.yml logs -f api_server

# View last 50 lines
docker compose -f docker-compose.yml -f docker-compose.dev.yml -f docker-compose.hotreload.yml logs --tail=50 web_server

# View logs without timestamps/service names
docker compose -f docker-compose.yml -f docker-compose.dev.yml -f docker-compose.hotreload.yml logs --no-log-prefix web_server
```

### Stopping & Restarting

```bash
# Stop all services (containers remain, can be started again)
docker compose -f docker-compose.yml -f docker-compose.dev.yml -f docker-compose.hotreload.yml stop

# Start stopped services
docker compose -f docker-compose.yml -f docker-compose.dev.yml -f docker-compose.hotreload.yml start

# Restart all services
docker compose -f docker-compose.yml -f docker-compose.dev.yml -f docker-compose.hotreload.yml restart

# Restart specific service
docker compose -f docker-compose.yml -f docker-compose.dev.yml -f docker-compose.hotreload.yml restart web_server
docker compose -f docker-compose.yml -f docker-compose.dev.yml -f docker-compose.hotreload.yml restart api_server

# Stop and remove all containers (clean shutdown)
docker compose -f docker-compose.yml -f docker-compose.dev.yml -f docker-compose.hotreload.yml down

# Stop and remove containers + volumes (DANGEROUS - deletes data!)
docker compose -f docker-compose.yml -f docker-compose.dev.yml -f docker-compose.hotreload.yml down -v
```

### Rebuilding After Code Changes

```bash
# Rebuild specific service (after changing Dockerfile or dependencies)
docker compose -f docker-compose.yml -f docker-compose.dev.yml -f docker-compose.hotreload.yml up -d --build web_server

# Rebuild all services
docker compose -f docker-compose.yml -f docker-compose.dev.yml -f docker-compose.hotreload.yml up -d --build

# Force recreate without cache (nuclear option)
docker compose -f docker-compose.yml -f docker-compose.dev.yml -f docker-compose.hotreload.yml build --no-cache
docker compose -f docker-compose.yml -f docker-compose.dev.yml -f docker-compose.hotreload.yml up -d --force-recreate
```

---

## Troubleshooting Commands

### Container is Unhealthy or Failing

```bash
# Check health status details
docker inspect onyx-web_server-1 --format='{{json .State.Health}}' | python3 -m json.tool

# Check what's happening inside container
docker compose -f docker-compose.yml -f docker-compose.dev.yml -f docker-compose.hotreload.yml logs web_server --tail=100

# Execute health check manually
docker exec onyx-web_server-1 node -e "require('http').get('http://127.0.0.1:3000/', (r) => process.exit(r.statusCode < 500 ? 0 : 1))"

# Get shell access to debug
docker exec -it onyx-web_server-1 sh
docker exec -it onyx-api_server-1 bash
```

### Dependencies Not Installing

```bash
# Frontend - reinstall node_modules
docker compose -f docker-compose.yml -f docker-compose.dev.yml -f docker-compose.hotreload.yml exec web_server bun install --frozen-lockfile

# Backend - reinstall Python packages
docker compose -f docker-compose.yml -f docker-compose.dev.yml -f docker-compose.hotreload.yml exec api_server uv pip install --system -r requirements/default.txt
```

### Port Conflicts

```bash
# Check what's using a port
sudo lsof -i :3000
sudo lsof -i :8080

# Kill process using port
sudo kill -9 <PID>
```

### Network Issues

```bash
# Check Docker networks
docker network ls

# Inspect network
docker network inspect onyx_default

# Check which containers are on network
docker network inspect onyx_default --format='{{range .Containers}}{{.Name}} {{end}}'

# Reconnect container to network
docker network connect onyx_default onyx-nginx-1
```

### Database Issues

```bash
# Connect to PostgreSQL
docker exec -it onyx-relational_db-1 psql -U postgres

# Run SQL query
docker exec -it onyx-relational_db-1 psql -U postgres -c "SELECT * FROM pg_stat_activity;"

# Check database size
docker exec -it onyx-relational_db-1 psql -U postgres -c "\l+"

# Run Alembic migrations manually
docker compose -f docker-compose.yml -f docker-compose.dev.yml -f docker-compose.hotreload.yml exec api_server alembic upgrade head
```

### Disk Space Issues

```bash
# Check disk usage
df -h
docker system df

# Clean up unused images
docker image prune -a

# Clean up unused volumes
docker volume prune

# Clean up everything (DANGEROUS)
docker system prune -a --volumes
```

### Memory Issues

```bash
# Check container resource usage
docker stats --no-stream

# Check container with specific format
docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}"

# Restart container if out of memory
docker compose -f docker-compose.yml -f docker-compose.dev.yml -f docker-compose.hotreload.yml restart <service_name>
```

---

## Environment Configuration

### Viewing Environment Variables

```bash
# View .env file
cat /home/analemma/dev/haqqai/deployment/docker_compose/.env

# Check environment variables in running container
docker compose -f docker-compose.yml -f docker-compose.dev.yml -f docker-compose.hotreload.yml exec api_server env

# Check specific variable
docker compose -f docker-compose.yml -f docker-compose.dev.yml -f docker-compose.hotreload.yml exec api_server printenv POSTGRES_HOST
```

### Editing Environment Variables

```bash
# Edit .env file
nano /home/analemma/dev/haqqai/deployment/docker_compose/.env

# After editing, recreate containers to apply changes
docker compose -f docker-compose.yml -f docker-compose.dev.yml -f docker-compose.hotreload.yml up -d --force-recreate
```

---

## Database Operations

### Backup & Restore

```bash
# Backup database
docker exec onyx-relational_db-1 pg_dump -U postgres onyx > backup_$(date +%Y%m%d_%H%M).sql

# Restore database
cat backup_20260608_1200.sql | docker exec -i onyx-relational_db-1 psql -U postgres onyx

# Backup to compressed file
docker exec onyx-relational_db-1 pg_dump -U postgres onyx | gzip > backup_$(date +%Y%m%d_%H%M).sql.gz
```

### Database Access

```bash
# Interactive psql session
docker exec -it onyx-relational_db-1 psql -U postgres onyx

# Run single SQL command
docker exec -it onyx-relational_db-1 psql -U postgres onyx -c "SELECT COUNT(*) FROM users;"

# List all databases
docker exec -it onyx-relational_db-1 psql -U postgres -c "\l"

# List all tables
docker exec -it onyx-relational_db-1 psql -U postgres onyx -c "\dt"
```

---

## Advanced Operations

### Scaling Services

```bash
# Run multiple instances of a service (for testing load balancing)
docker compose -f docker-compose.yml -f docker-compose.dev.yml -f docker-compose.hotreload.yml up -d --scale background=3
```

### Volume Management

```bash
# List volumes
docker volume ls | grep onyx

# Inspect volume
docker volume inspect onyx_db_volume

# Remove specific volume (DANGEROUS - deletes data!)
docker volume rm onyx_db_volume

# Backup volume
docker run --rm -v onyx_db_volume:/data -v $(pwd):/backup alpine tar czf /backup/db_backup.tar.gz /data
```

### Image Management

```bash
# List images
docker images | grep onyx

# Remove specific image
docker rmi onyx-web-dev:local

# Pull latest images
docker compose -f docker-compose.yml -f docker-compose.dev.yml -f docker-compose.hotreload.yml pull

# Build without starting
docker compose -f docker-compose.yml -f docker-compose.dev.yml -f docker-compose.hotreload.yml build
```

---

## Useful Aliases

Add these to your `~/.bashrc` or `~/.zshrc`:

```bash
# Navigate to docker compose directory
alias cddc='cd /home/analemma/dev/haqqai/deployment/docker_compose'

# Docker compose with all config files
alias dcdev='docker compose -f docker-compose.yml -f docker-compose.dev.yml -f docker-compose.hotreload.yml'

# Common operations
alias dcup='dcdev up -d'
alias dcdown='dcdev down'
alias dcps='dcdev ps'
alias dclogs='dcdev logs -f'
alias dcrestart='dcdev restart'

# Usage after adding aliases:
# cddc && dcup
# dclogs web_server
# dcrestart api_server
```

After adding, run: `source ~/.bashrc` or `source ~/.zshrc`

---

## Common Issues & Solutions

### Issue: web_server is unhealthy

**Cause:** The container is starting but the health check is failing.

**Solution:**
```bash
# Check if Next.js dev server is actually running
docker compose -f docker-compose.yml -f docker-compose.dev.yml -f docker-compose.hotreload.yml logs web_server --tail=50

# If you see "Ready in Xms", the server is running
# Wait 1-2 minutes for health check to pass, or manually test:
curl http://localhost:3000

# If it responds, the container will eventually become healthy
```

### Issue: Changes not reflecting

**Frontend changes:**
- Hot-reload should be automatic
- Check if bun dev server is running: `docker compose -f docker-compose.yml -f docker-compose.dev.yml -f docker-compose.hotreload.yml logs web_server`
- Hard refresh browser: Ctrl+Shift+R (Linux/Windows) or Cmd+Shift+R (Mac)

**Backend changes:**
- Hot-reload should be automatic with uvicorn --reload
- Check logs: `docker compose -f docker-compose.yml -f docker-compose.dev.yml -f docker-compose.hotreload.yml logs api_server`
- If not reloading, restart: `docker compose -f docker-compose.yml -f docker-compose.dev.yml -f docker-compose.hotreload.yml restart api_server`

**Dockerfile or dependency changes:**
- Rebuild: `docker compose -f docker-compose.yml -f docker-compose.dev.yml -f docker-compose.hotreload.yml up -d --build`

### Issue: nginx failing to start

**For local development, you don't need nginx!**

Access services directly:
- Frontend: http://localhost:3000
- Backend API: http://localhost:8080

If you really need nginx for production-like setup, the issue is DNS resolution. The workaround is to use production setup or fix the nginx configuration.

### Issue: Port already in use

```bash
# Find what's using the port
sudo lsof -i :3000

# Kill the process
sudo kill -9 <PID>

# Or change the port in docker-compose.dev.yml
```

### Issue: Out of disk space

```bash
# Check disk usage
df -h
docker system df

# Clean up
docker system prune -a
docker volume prune

# Remove specific old images
docker images | grep onyx
docker rmi <IMAGE_ID>
```

---

## Production Deployment

For production, use the standard compose file without dev/hotreload:

```bash
cd /home/analemma/dev/haqqai/deployment/docker_compose

# Production deployment
docker compose -f docker-compose.yml up -d

# With production nginx config
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

---

## Testing Commands

### Running Tests

```bash
# Navigate to repo root
cd /home/analemma/dev/haqqai

# Activate virtual environment
source .venv/bin/activate

# Run unit tests
pytest -xv backend/tests/unit

# Run external dependency unit tests
python -m dotenv -f .vscode/.env run -- pytest backend/tests/external_dependency_unit

# Run integration tests
python -m dotenv -f .vscode/.env run -- pytest backend/tests/integration

# Run Playwright tests
cd web
bunx playwright test
```

---

## Emergency Procedures

### Complete Reset (Nuclear Option)

```bash
cd /home/analemma/dev/haqqai/deployment/docker_compose

# Stop everything
docker compose -f docker-compose.yml -f docker-compose.dev.yml -f docker-compose.hotreload.yml down

# Remove all Onyx containers, images, and volumes
docker compose -f docker-compose.yml -f docker-compose.dev.yml -f docker-compose.hotreload.yml down -v --rmi all

# Clean up Docker system
docker system prune -a --volumes

# Rebuild from scratch
docker compose -f docker-compose.yml -f docker-compose.dev.yml -f docker-compose.hotreload.yml up -d --build
```

### Stuck Container

```bash
# Force remove
docker rm -f onyx-web_server-1

# Restart the service
docker compose -f docker-compose.yml -f docker-compose.dev.yml -f docker-compose.hotreload.yml up -d web_server
```

---

## Monitoring & Debugging

### Real-time Monitoring

```bash
# Watch container stats
watch -n 2 'docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}"'

# Watch logs
docker compose -f docker-compose.yml -f docker-compose.dev.yml -f docker-compose.hotreload.yml logs -f | grep ERROR
```

### Export Logs

```bash
# Export all logs to file
docker compose -f docker-compose.yml -f docker-compose.dev.yml -f docker-compose.hotreload.yml logs > all_logs_$(date +%Y%m%d_%H%M).txt

# Export specific service logs
docker compose -f docker-compose.yml -f docker-compose.dev.yml -f docker-compose.hotreload.yml logs api_server > api_logs_$(date +%Y%m%d_%H%M).txt
```

---

## Important Notes

1. **Hot-reload is enabled** - Your code changes will be reflected immediately without rebuilding
2. **node_modules in named volume** - Don't delete the `web_node_modules` volume or you'll need to reinstall all dependencies
3. **First startup is slow** - Dependencies need to be downloaded and installed
4. **Subsequent startups are fast** - Cached in volumes
5. **Don't use nginx in dev** - Access services directly for better debugging
6. **Always use all three compose files** - The base + dev + hotreload configuration
7. **Check .env file** - Make sure it has correct configuration (OpenAI key, etc.)

---

## Quick Start Checklist

- [ ] Navigate to: `cd /home/analemma/dev/haqqai/deployment/docker_compose`
- [ ] Ensure `.env` file exists and is configured
- [ ] Start services: `docker compose -f docker-compose.yml -f docker-compose.dev.yml -f docker-compose.hotreload.yml up -d --build`
- [ ] Wait 2-3 minutes for services to start
- [ ] Check status: `docker compose -f docker-compose.yml -f docker-compose.dev.yml -f docker-compose.hotreload.yml ps`
- [ ] Open frontend: http://localhost:3000
- [ ] Make code changes and see them live!

---

## Getting Help

```bash
# Docker compose help
docker compose --help

# Service-specific help
docker compose -f docker-compose.yml -f docker-compose.dev.yml -f docker-compose.hotreload.yml --help

# Check Docker version
docker --version
docker compose version
```
