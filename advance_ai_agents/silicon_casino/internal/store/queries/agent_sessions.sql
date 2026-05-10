-- name: CreateAgentSession :exec
INSERT INTO agent_sessions (id, agent_id, room_id, table_id, seat_id, join_mode, status, expires_at)
VALUES (
  sqlc.arg(id),
  sqlc.arg(agent_id),
  sqlc.arg(room_id),
  NULLIF(sqlc.arg(table_id)::text, ''),
  sqlc.arg(seat_id),
  sqlc.arg(join_mode),
  sqlc.arg(status),
  sqlc.arg(expires_at)
);

-- name: GetAgentSessionByID :one
SELECT id, agent_id, room_id, table_id, seat_id, join_mode, status, expires_at, created_at, closed_at
FROM agent_sessions
WHERE id = $1;

-- name: UpdateAgentSessionMatch :execrows
UPDATE agent_sessions
SET table_id = $2, seat_id = $3, status = 'active'
WHERE id = $1;

-- name: CloseAgentSession :execrows
UPDATE agent_sessions
SET status = 'closed', closed_at = now()
WHERE id = $1 AND status <> 'closed';

-- name: CloseAgentSessionsByTableID :execrows
UPDATE agent_sessions
SET status = 'closed', closed_at = now()
WHERE table_id = $1::text AND status <> 'closed';

-- name: InsertAgentActionRequestIfAbsent :execrows
INSERT INTO agent_action_requests (id, session_id, request_id, turn_id, action_type, amount_cc, thought_log, accepted, reason)
VALUES (
  sqlc.arg(id),
  sqlc.arg(session_id),
  sqlc.arg(request_id),
  sqlc.arg(turn_id),
  sqlc.arg(action_type),
  sqlc.arg(amount_cc),
  NULLIF(sqlc.arg(thought_log)::text, ''),
  sqlc.arg(accepted),
  NULLIF(sqlc.arg(reason)::text, '')
)
ON CONFLICT (session_id, request_id) DO NOTHING;

-- name: GetAgentActionRequestBySessionAndRequest :one
SELECT id, session_id, request_id, turn_id, action_type, amount_cc, thought_log, accepted, reason, created_at
FROM agent_action_requests
WHERE session_id = $1 AND request_id = $2;

-- name: CountAgentActionRequestsBySessionAndRequest :one
SELECT COUNT(*)::int
FROM agent_action_requests
WHERE session_id = $1 AND request_id = $2;

-- name: UpsertAgentEventOffset :exec
INSERT INTO agent_event_offsets (session_id, last_event_id)
VALUES ($1, $2)
ON CONFLICT (session_id)
DO UPDATE SET last_event_id = EXCLUDED.last_event_id, updated_at = now();

-- name: GetAgentEventOffsetBySessionID :one
SELECT session_id, last_event_id, updated_at
FROM agent_event_offsets
WHERE session_id = $1;

-- name: CountAgentSessions :one
SELECT COUNT(*)::int
FROM agent_sessions;
