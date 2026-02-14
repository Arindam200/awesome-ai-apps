# Go Backend Refactor Migration Notes

## What changed

- HTTP business handlers were moved out of `cmd/game-server` into `internal/transport/http`.
- Domain orchestration was introduced under `internal/app/agent`, `internal/app/public`, and `internal/app/session`.
- Store access methods were split from one large file into domain-specific repository files in `internal/store`.
- `internal/agentgateway/coordinator.go` was split into focused coordinator files.
- SQL named args were normalized in `internal/store/queries/*.sql` and regenerated via `make sqlc`.

## Compatibility intent

- Public HTTP paths remain unchanged.
- Existing JSON field names remain unchanged.
- SSE behavior and expvar metric names remain unchanged.

## New package boundaries

- `cmd/game-server`: startup and dependency wiring only.
- `internal/transport/http`: request/response mapping, middleware, route registration.
- `internal/app/*`: domain services and error contracts.
- `internal/store`: persistence facade and repositories.

## Extension constraints

- Do not put business logic back into `cmd/*`.
- Keep transport concerns in `internal/transport/http` only.
- New domain logic should go into `internal/app/<domain>`.
- Keep SQL only in `internal/store/queries/*.sql`, then regenerate sqlc code.
- Keep repository methods grouped by domain file; do not re-introduce a monolithic repository file.

## Migration checklist for future changes

- Add/modify SQL in query files and run `make sqlc`.
- Implement/update store repository method.
- Add/update app service method and domain errors.
- Bind handler mapping in `internal/transport/http`.
- Add/adjust route snapshot and contract tests.
- Run `make lint` and `go test ./...`.
