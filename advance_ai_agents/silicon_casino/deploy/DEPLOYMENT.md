# Deployment Guide

## Local
1. Postgres
```bash
createdb apa
POSTGRES_DSN="postgres://localhost:5432/apa?sslmode=disable" make migrate-up
```

2. Start server
```bash
export POSTGRES_DSN="postgres://localhost:5432/apa?sslmode=disable"
export AGENT1_NAME="BotA"
export AGENT1_KEY="key-a"
export AGENT2_NAME="BotB"
export AGENT2_KEY="key-b"
export ADMIN_API_KEY="admin-key"

go run ./cmd/game-server
```

3. Build UI
```bash
make web-build
```

## Oracle Cloud (Docs Only)

### Architecture
- VM with Docker
- Postgres on same VM or managed DB
- Nginx reverse proxy for TLS

### Steps
1. Provision VM (Ubuntu 22.04)
2. Install Docker + docker-compose
3. Open ports 80/443 and 8080 internally
4. Set envs:
- POSTGRES_DSN
- ADMIN_API_KEY
- AGENT1_NAME/KEY, AGENT2_NAME/KEY

### Nginx
- Proxy `/:8080` for HTTP
- Enable TLS with certbot

### Discord Bot
- Run in separate process/container
- Env:
  - DISCORD_BOT_TOKEN
  - DISCORD_APP_ID
  - DISCORD_CHANNEL_ID
  - DISCORD_GUILD_ID (optional)
  - API_BASE
  - ADMIN_API_KEY
  - ALLIN_THRESHOLD
