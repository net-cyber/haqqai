#!/bin/bash
# Docker Development Aliases for Haqqai/Onyx
# Add this to your ~/.bashrc or ~/.zshrc by running:
# echo "source /home/analemma/dev/haqqai/deployment/docker_compose/docker-dev-aliases.sh" >> ~/.bashrc

# Navigate to docker compose directory
alias cddc='cd /home/analemma/dev/haqqai/deployment/docker_compose'

# Base docker compose command with all config files
alias dcdev='docker compose -f docker-compose.yml -f docker-compose.dev.yml -f docker-compose.hotreload.yml'

# Common operations
alias dcup='dcdev up -d'
alias dcdown='dcdev down'
alias dcps='dcdev ps'
alias dclogs='dcdev logs -f'
alias dcrestart='dcdev restart'
alias dcbuild='dcdev up -d --build'

# Service-specific logs
alias dclogsweb='dcdev logs -f web_server'
alias dclogsapi='dcdev logs -f api_server'
alias dclogsbg='dcdev logs -f background'
alias dclogsdb='dcdev logs -f relational_db'

# Service-specific restart
alias dcrestartweb='dcdev restart web_server'
alias dcrestartapi='dcdev restart api_server'
alias dcrestartbg='dcdev restart background'

# Health checks
alias dchealth='dcdev ps --format "table {{.Name}}\t{{.Status}}"'

# Quick access to services
alias dcexecweb='docker exec -it onyx-web_server-1 sh'
alias dcexecapi='docker exec -it onyx-api_server-1 bash'
alias dcexecdb='docker exec -it onyx-relational_db-1 psql -U postgres onyx'

# System cleanup
alias dcclean='docker system prune -f'
alias dccleanall='docker system prune -af --volumes'

echo "✅ Haqqai Docker Development aliases loaded!"
echo "📚 Available commands:"
echo "  cddc          - Navigate to docker compose directory"
echo "  dcdev         - Base docker compose command"
echo "  dcup          - Start all services"
echo "  dcdown        - Stop all services"
echo "  dcps          - Show service status"
echo "  dclogs        - Follow all logs"
echo "  dclogsweb     - Follow web server logs"
echo "  dclogsapi     - Follow API server logs"
echo "  dcrestart     - Restart all services"
echo "  dcrestartweb  - Restart web server"
echo "  dcrestartapi  - Restart API server"
echo "  dcbuild       - Rebuild and start all services"
echo "  dchealth      - Show health status"
echo "  dcexecweb     - Shell into web server"
echo "  dcexecapi     - Shell into API server"
echo "  dcexecdb      - Connect to PostgreSQL"
echo "  dcclean       - Clean up Docker system"
