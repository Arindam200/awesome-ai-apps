.PHONY: dev test lint web-build dev-all sqlc migrate-up migrate-down migrate-force migrate-version migrate-create docker-build docker-up docker-down docker-logs

MIGRATE ?= migrate
MIGRATIONS_DIR ?= migrations

dev:
	POSTGRES_DSN=$${POSTGRES_DSN:-postgres://localhost:5432/apa?sslmode=disable} \
		go run ./cmd/game-server

test:
	go test ./...

lint:
	@if command -v golangci-lint >/dev/null 2>&1; then \
		golangci-lint run ./...; \
	else \
		GOCACHE=$${GOCACHE:-/tmp/go-build} go test ./...; \
	fi

sqlc:
	CGO_ENABLED=0 go run github.com/sqlc-dev/sqlc/cmd/sqlc@v1.27.0 generate

web-build:
	cd web && npm install && npm run build

dev-all:
	@echo "Run in terminal:"
	@echo "  make dev"

migrate-up:
	@test -n "$(POSTGRES_DSN)" || (echo "POSTGRES_DSN is required"; exit 1)
	$(MIGRATE) -path $(MIGRATIONS_DIR) -database "$(POSTGRES_DSN)" up

migrate-down:
	@test -n "$(POSTGRES_DSN)" || (echo "POSTGRES_DSN is required"; exit 1)
	$(MIGRATE) -path $(MIGRATIONS_DIR) -database "$(POSTGRES_DSN)" down 1

migrate-force:
	@test -n "$(POSTGRES_DSN)" || (echo "POSTGRES_DSN is required"; exit 1)
	@test -n "$(version)" || (echo "version is required, usage: make migrate-force version=1"; exit 1)
	$(MIGRATE) -path $(MIGRATIONS_DIR) -database "$(POSTGRES_DSN)" force $(version)

migrate-version:
	@test -n "$(POSTGRES_DSN)" || (echo "POSTGRES_DSN is required"; exit 1)
	$(MIGRATE) -path $(MIGRATIONS_DIR) -database "$(POSTGRES_DSN)" version

migrate-create:
	@test -n "$(name)" || (echo "name is required, usage: make migrate-create name=add_xxx"; exit 1)
	$(MIGRATE) create -ext sql -dir $(MIGRATIONS_DIR) -seq $(name)

docker-build:
	docker compose build

docker-up:
	docker compose up -d

docker-down:
	docker compose down

docker-logs:
	docker compose logs -f app
