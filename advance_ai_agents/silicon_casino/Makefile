.PHONY: dev test web-build dev-all sqlc migrate-up migrate-down migrate-force migrate-version migrate-create

MIGRATE ?= migrate
MIGRATIONS_DIR ?= migrations

dev:
	POSTGRES_DSN=$${POSTGRES_DSN:-postgres://localhost:5432/apa?sslmode=disable} \
	AGENT1_NAME=$${AGENT1_NAME:-BotA} AGENT1_KEY=$${AGENT1_KEY:-key-a} \
	AGENT2_NAME=$${AGENT2_NAME:-BotB} AGENT2_KEY=$${AGENT2_KEY:-key-b} \
		go run ./cmd/game-server

test:
	go test ./...

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
