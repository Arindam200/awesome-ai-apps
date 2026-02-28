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
export ADMIN_API_KEY="admin-key"

go run ./cmd/game-server
```

3. Build UI
```bash
make web-build
```

## Docker

1. Copy `.env.example` to `.env` and adjust values as needed:
```bash
cp .env.example .env
```

2. Build and start all services:
```bash
make docker-up
# or: docker compose up -d
```

This starts:
- **PostgreSQL 16** with a `pgdata` volume for persistence
- **golang-migrate** to apply schema migrations automatically
- **game-server** with the built-in spectator UI

3. Check logs:
```bash
make docker-logs
```

4. Stop all services:
```bash
make docker-down
# Add -v to also remove the DB volume: docker compose down -v
```

5. Rebuild after code changes:
```bash
make docker-build
make docker-up
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

### Nginx
- Proxy `/:8080` for HTTP
- Enable TLS with certbot

### Spectator Push (Discord / Feishu)
- Built into the game server process (no separate bot process needed).
- Env:
  - SPECTATOR_PUSH_ENABLED=true
  - SPECTATOR_PUSH_CONFIG_PATH=./deploy/spectator-push.targets.json
