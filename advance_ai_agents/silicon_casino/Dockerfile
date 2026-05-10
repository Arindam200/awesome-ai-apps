# ── Stage 1: build frontend ────────────────────────────────────────
FROM node:20-alpine AS builder-web
WORKDIR /src/web
COPY web/package.json ./
RUN npm install
COPY web/ ./
COPY internal/ /src/internal/
RUN npm run build
# Output lands in /src/internal/web/static (per vite.config.js)

# ── Stage 2: build Go binary ──────────────────────────────────────
FROM golang:1.22-alpine AS builder-go
RUN apk add --no-cache git
WORKDIR /src
COPY go.mod go.sum ./
RUN go mod download
COPY . .
# Bring in the built frontend assets from Stage 1
COPY --from=builder-web /src/internal/web/static /src/internal/web/static
RUN CGO_ENABLED=0 GOOS=linux go build -trimpath -ldflags="-s -w" -o /app/game-server ./cmd/game-server

# ── Stage 3: minimal runtime ─────────────────────────────────────
FROM alpine:3.19 AS runtime
RUN apk add --no-cache ca-certificates tzdata
WORKDIR /app

COPY --from=builder-go /app/game-server ./game-server
COPY migrations/ ./migrations/
COPY deploy/ ./deploy/
# Static files must be at internal/web/static relative to the working dir
COPY --from=builder-web /src/internal/web/static ./internal/web/static/

EXPOSE 8080
ENTRYPOINT ["./game-server"]
