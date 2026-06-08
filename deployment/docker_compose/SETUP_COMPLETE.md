# ✅ Development Environment Setup Complete!

## Current Status

Your Haqqai/Onyx development environment with **hot-reload** is now running successfully!

### 🟢 Services Running

| Service | Status | Access URL |
|---------|--------|------------|
| **Frontend (Next.js)** | ✅ Healthy | http://localhost:3000 |
| **Backend API** | ✅ Healthy | http://localhost:8080 |
| **PostgreSQL** | ✅ Healthy | localhost:5434 |
| **Redis** | ✅ Running | localhost:6379 |
| **OpenSearch** | ✅ Running | localhost:9200 |
| **MinIO S3** | ✅ Healthy | localhost:9004 (API), localhost:9005 (Console) |
| **Model Servers** | ✅ Healthy | localhost:9000 |
| **Background Workers** | ✅ Running | - |

### ⚠️ Known Issues

- **Nginx**: Not needed for local development. Access services directly via their ports above.
  - If you need nginx for production-like testing, you'll need to fix DNS resolution issues.
  - For development, just use the direct ports listed above.

---

## 🎯 How to Use

### Make Code Changes

1. **Frontend Changes** (web/)
   - Edit any file in `/home/analemma/dev/haqqai/web/`
   - Changes will be automatically detected by Next.js dev server
   - Browser will hot-reload automatically
   - No rebuild needed!

2. **Backend Changes** (backend/)
   - Edit any file in `/home/analemma/dev/haqqai/backend/`
   - uvicorn will automatically detect changes and reload
   - API will restart automatically
   - No rebuild needed!

3. **Dependency Changes**
   - Frontend: Edit `package.json` then run:
     ```bash
     docker compose -f docker-compose.yml -f docker-compose.dev.yml -f docker-compose.hotreload.yml exec web_server bun install
     ```
   - Backend: Edit requirements files then rebuild:
     ```bash
     docker compose -f docker-compose.yml -f docker-compose.dev.yml -f docker-compose.hotreload.yml up -d --build api_server
     ```

4. **Dockerfile Changes**
   - Always requires rebuild:
     ```bash
     docker compose -f docker-compose.yml -f docker-compose.dev.yml -f docker-compose.hotreload.yml up -d --build
     ```

---

## 📚 Documentation

- **[DOCKER_COMMANDS.md](DOCKER_COMMANDS.md)** - Complete reference for all Docker commands
- **[docker-dev-aliases.sh](docker-dev-aliases.sh)** - Convenient bash aliases
- **[README.md](README.md)** - General overview and production deployment
- **[../../AGENTS.md](../../AGENTS.md)** - Project-wide development guidelines

---

## 🚀 Quick Commands

### Daily Usage

```bash
# Navigate to docker compose directory
cd /home/analemma/dev/haqqai/deployment/docker_compose

# Check status
docker compose -f docker-compose.yml -f docker-compose.dev.yml -f docker-compose.hotreload.yml ps

# View logs
docker compose -f docker-compose.yml -f docker-compose.dev.yml -f docker-compose.hotreload.yml logs -f

# View specific service logs
docker compose -f docker-compose.yml -f docker-compose.dev.yml -f docker-compose.hotreload.yml logs -f web_server
docker compose -f docker-compose.yml -f docker-compose.dev.yml -f docker-compose.hotreload.yml logs -f api_server

# Restart if needed
docker compose -f docker-compose.yml -f docker-compose.dev.yml -f docker-compose.hotreload.yml restart web_server
docker compose -f docker-compose.yml -f docker-compose.dev.yml -f docker-compose.hotreload.yml restart api_server

# Stop everything
docker compose -f docker-compose.yml -f docker-compose.dev.yml -f docker-compose.hotreload.yml down

# Start again
docker compose -f docker-compose.yml -f docker-compose.dev.yml -f docker-compose.hotreload.yml up -d
```

### Install Convenient Aliases (Recommended!)

```bash
# Add aliases to your shell
echo "source /home/analemma/dev/haqqai/deployment/docker_compose/docker-dev-aliases.sh" >> ~/.bashrc
source ~/.bashrc

# Now you can use short commands:
cddc           # Navigate to docker compose directory
dcup           # Start all services
dcps           # Check status
dclogs         # View logs
dclogsweb      # View web server logs
dclogsapi      # View API server logs
dcrestart      # Restart all
dcrestartweb   # Restart web server
dcrestartapi   # Restart API server
dcdown         # Stop all
```

---

## 🔧 Common Tasks

### Adding a New User

Since the issue mentioned "why can't i add a user in the portal", here's how to debug:

1. Check if the API is accessible:
   ```bash
   curl http://localhost:8080/health
   ```

2. Check API logs for errors:
   ```bash
   docker compose -f docker-compose.yml -f docker-compose.dev.yml -f docker-compose.hotreload.yml logs api_server --tail=100
   ```

3. Check if authentication is configured in `.env`:
   ```bash
   cat .env | grep AUTH_TYPE
   ```

4. Access the database to check users:
   ```bash
   docker exec -it onyx-relational_db-1 psql -U postgres onyx -c "SELECT id, email, role FROM \"user\";"
   ```

### Database Access

```bash
# Connect to PostgreSQL
docker exec -it onyx-relational_db-1 psql -U postgres onyx

# Run a query
docker exec -it onyx-relational_db-1 psql -U postgres onyx -c "SELECT * FROM \"user\";"

# Backup database
docker exec onyx-relational_db-1 pg_dump -U postgres onyx > backup_$(date +%Y%m%d_%H%M).sql
```

### Viewing Environment Variables

```bash
# View .env file
cat /home/analemma/dev/haqqai/deployment/docker_compose/.env

# Check variables in container
docker compose -f docker-compose.yml -f docker-compose.dev.yml -f docker-compose.hotreload.yml exec api_server env
```

---

## 🐛 Troubleshooting

### Container is Unhealthy

```bash
# Check logs
docker compose -f docker-compose.yml -f docker-compose.dev.yml -f docker-compose.hotreload.yml logs <service_name> --tail=100

# Check health details
docker inspect onyx-<service_name>-1 --format='{{json .State.Health}}' | python3 -m json.tool

# Restart the service
docker compose -f docker-compose.yml -f docker-compose.dev.yml -f docker-compose.hotreload.yml restart <service_name>
```

### Changes Not Reflecting

**Frontend:**
- Hard refresh: Ctrl+Shift+R (Linux/Windows) or Cmd+Shift+R (Mac)
- Check if dev server is running: `docker compose -f docker-compose.yml -f docker-compose.dev.yml -f docker-compose.hotreload.yml logs web_server`

**Backend:**
- Check if uvicorn detected the change: `docker compose -f docker-compose.yml -f docker-compose.dev.yml -f docker-compose.hotreload.yml logs api_server`
- Restart if needed: `docker compose -f docker-compose.yml -f docker-compose.dev.yml -f docker-compose.hotreload.yml restart api_server`

### Port Conflicts

```bash
# Check what's using a port
sudo lsof -i :3000

# Kill the process
sudo kill -9 <PID>
```

### Complete Reset (Nuclear Option)

```bash
# Stop and remove everything
docker compose -f docker-compose.yml -f docker-compose.dev.yml -f docker-compose.hotreload.yml down -v

# Clean Docker system
docker system prune -a

# Rebuild from scratch
docker compose -f docker-compose.yml -f docker-compose.dev.yml -f docker-compose.hotreload.yml up -d --build
```

---

## 🎓 Next Steps

1. **Explore the Frontend**: Open http://localhost:3000
2. **Check the API**: Open http://localhost:8080/docs (FastAPI Swagger UI)
3. **Make a Test Change**: Edit a file in `web/` or `backend/` and see it reload
4. **Read the Docs**: Check [DOCKER_COMMANDS.md](DOCKER_COMMANDS.md) for more commands
5. **Install Aliases**: Make your life easier with the convenience aliases
6. **Configure Environment**: Review and update `.env` file as needed

---

## 📊 Health Check

Run this to verify everything is working:

```bash
cd /home/analemma/dev/haqqai/deployment/docker_compose

echo "=== Container Status ==="
docker compose -f docker-compose.yml -f docker-compose.dev.yml -f docker-compose.hotreload.yml ps

echo ""
echo "=== Frontend Health ==="
curl -s -o /dev/null -w "Status: %{http_code}\n" http://localhost:3000

echo ""
echo "=== Backend Health ==="
curl -s http://localhost:8080/health

echo ""
echo "=== All Good! 🎉 ==="
```

---

## 💡 Tips

1. **Always use all three compose files** for development (base + dev + hotreload)
2. **Don't use nginx in development** - Access services directly
3. **First startup takes 2-3 minutes** - Dependencies need to download
4. **Subsequent startups are fast** - Everything is cached
5. **Check logs if something fails** - They're very helpful
6. **Use the aliases** - They make life much easier
7. **Keep .env configured** - Especially API keys

---

## 🆘 Getting Help

1. Check [DOCKER_COMMANDS.md](DOCKER_COMMANDS.md) for command reference
2. Check [../../AGENTS.md](../../AGENTS.md) for project guidelines
3. View logs: `docker compose -f docker-compose.yml -f docker-compose.dev.yml -f docker-compose.hotreload.yml logs -f`
4. Check container health: `docker compose -f docker-compose.yml -f docker-compose.dev.yml -f docker-compose.hotreload.yml ps`
5. Google the error message
6. Ask in the team channel

---

**Happy Coding! 🚀**
