# Go Backend Refactor Guidelines

This repository follows a domain-first backend layout and strict compatibility rules.

## Package and layering rules

- `cmd/*` is bootstrap only: load config, wire dependencies, start server.
- HTTP transport is in `internal/transport/http`.
- Domain application services are in `internal/app/<domain>`.
- Infrastructure remains in `internal/store`, `internal/config`, and `internal/logging`.
- Dependency direction: `transport -> app -> store/game/ledger`.
- Application packages must not depend on transport packages.

## Naming rules

- Use short lowercase package names.
- Use capability-oriented file names: `service.go`, `handler.go`, `errors.go`, `repository_*.go`.
- Avoid generic package/file names like `util`, `common`, and `helpers`.

## Handler rules

- Handlers only do decode/validate/invoke service/encode.
- Keep public JSON contract stable unless explicitly versioned.
- Use typed DTOs instead of large ad-hoc `map[string]any` payload composition.

## Error rules

- Define domain errors in `errors.go` for each app package.
- Map errors to HTTP status at the transport boundary.
- Avoid string matching for cross-layer error contracts.

## SQL rules

- SQL must live under `internal/store/queries/*.sql`.
- No inline SQL in Go code.
- Query names should use explicit `VerbNoun...` style.
- Prefer `sqlc.arg(...)` to avoid generated placeholder names like `Column1`.

## Testing rules

- Keep behavior equivalent during refactor.
- Run `go test ./...` for regression.
- Preserve route compatibility and SSE behavior.
- Keep sqlc-backed store tests passing.

## Observability rules

- Preserve existing expvar metrics names and semantics.
- Do not regress request logging or SSE heartbeat behavior.
