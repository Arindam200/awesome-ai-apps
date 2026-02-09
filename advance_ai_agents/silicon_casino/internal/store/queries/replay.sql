-- name: InsertTableReplayEvent :exec
INSERT INTO table_replay_events (
  id, table_id, hand_id, global_seq, hand_seq, event_type, actor_agent_id, payload, schema_version
)
VALUES ($1, $2, NULLIF($3::text, ''), $4, $5, $6, NULLIF($7::text, ''), $8::jsonb, $9);

-- name: ListTableReplayEventsFromSeq :many
SELECT id, table_id, hand_id, global_seq, hand_seq, event_type, actor_agent_id, payload, schema_version, created_at
FROM table_replay_events
WHERE table_id = $1
  AND global_seq >= $2
ORDER BY global_seq ASC
LIMIT $3;

-- name: GetTableReplayLastSeq :one
SELECT COALESCE(MAX(global_seq), 0)::bigint
FROM table_replay_events
WHERE table_id = $1;

-- name: InsertTableReplaySnapshot :exec
INSERT INTO table_replay_snapshots (id, table_id, at_global_seq, state_blob, schema_version)
VALUES ($1, $2, $3, $4::jsonb, $5);

-- name: GetLatestTableReplaySnapshotAtOrBefore :one
SELECT id, table_id, at_global_seq, state_blob, schema_version, created_at
FROM table_replay_snapshots
WHERE table_id = $1
  AND at_global_seq <= $2
ORDER BY at_global_seq DESC
LIMIT 1;

-- name: ListHandsByTableID :many
SELECT id, table_id, winner_agent_id, pot_cc, street_end, started_at, ended_at
FROM hands
WHERE table_id = $1
ORDER BY started_at ASC;

-- name: ListHandsByAgentID :many
SELECT h.id, h.table_id, h.winner_agent_id, h.pot_cc, h.street_end, h.started_at, h.ended_at
FROM hands h
JOIN actions a ON a.hand_id = h.id
WHERE a.agent_id = $1
GROUP BY h.id, h.table_id, h.winner_agent_id, h.pot_cc, h.street_end, h.started_at, h.ended_at
ORDER BY h.started_at DESC
LIMIT $2 OFFSET $3;

-- name: GetHandByID :one
SELECT id, table_id, winner_agent_id, pot_cc, street_end, started_at, ended_at
FROM hands
WHERE id = $1;

-- name: ListAgentTables :many
SELECT
  t.id,
  t.room_id,
  t.status,
  t.small_blind_cc,
  t.big_blind_cc,
  t.created_at,
  MAX(h.ended_at) AS last_hand_ended_at
FROM tables t
JOIN agent_sessions s ON s.table_id = t.id
LEFT JOIN hands h ON h.table_id = t.id
WHERE s.agent_id = $1
GROUP BY t.id, t.room_id, t.status, t.small_blind_cc, t.big_blind_cc, t.created_at
ORDER BY MAX(h.started_at) DESC NULLS LAST, t.created_at DESC
LIMIT $2 OFFSET $3;

-- name: ListTableHistory :many
SELECT
  t.id,
  t.room_id,
  t.status,
  t.small_blind_cc,
  t.big_blind_cc,
  t.created_at,
  MAX(h.ended_at) AS last_hand_ended_at
FROM tables t
LEFT JOIN hands h ON h.table_id = t.id
WHERE ($1::text = '' OR t.room_id = $1)
  AND (
    $2::text = ''
    OR EXISTS (
      SELECT 1
      FROM agent_sessions s
      WHERE s.table_id = t.id AND s.agent_id = $2
    )
  )
GROUP BY t.id, t.room_id, t.status, t.small_blind_cc, t.big_blind_cc, t.created_at
ORDER BY MAX(h.started_at) DESC NULLS LAST, t.created_at DESC
LIMIT $3 OFFSET $4;
