## Summary

- What changed?
- Why is this change needed?

## Behavior / API Impact

- Does this modify API behavior, event payloads, or error codes?
- If yes, list endpoint(s) and expected client impact.

## Verification

- [ ] `go test ./...`
- [ ] Manual smoke test completed

### Manual test notes

- Steps executed:
- Expected result:
- Actual result:

## Database / SQL

- [ ] No SQL changes
- [ ] SQL updated under `internal/store/queries/*.sql`
- [ ] `make sqlc` re-generated code

## Deployment Notes

- Any env var changes?
- Any migration/runtime ordering requirements?

## Checklist

- [ ] Branch name uses `codex/<topic>`
- [ ] Docs updated (README / protocol docs) if behavior changed
