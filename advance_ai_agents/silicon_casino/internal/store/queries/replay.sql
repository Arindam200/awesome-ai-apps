-- name: InsertTableReplayEvent :exec
INSERT INTO table_replay_events (
  id, table_id, hand_id, global_seq, hand_seq, event_type, actor_agent_id, payload, schema_version
)
VALUES (
  sqlc.arg(id),
  sqlc.arg(table_id),
  NULLIF(sqlc.arg(hand_id)::text, ''),
  sqlc.arg(global_seq),
  sqlc.arg(hand_seq),
  sqlc.arg(event_type),
  NULLIF(sqlc.arg(actor_agent_id)::text, ''),
  sqlc.arg(payload)::jsonb,
  sqlc.arg(schema_version)
);

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
VALUES (
  sqlc.arg(id),
  sqlc.arg(table_id),
  sqlc.arg(at_global_seq),
  sqlc.arg(state_blob)::jsonb,
  sqlc.arg(schema_version)
);

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
  r.name AS room_name,
  t.status,
  t.small_blind_cc,
  t.big_blind_cc,
  COUNT(h.id)::int AS hands_played,
  COALESCE(
    (
      SELECT jsonb_agg(
        jsonb_build_object(
          'agent_id', sp.agent_id,
          'agent_name', sp.agent_name
        )
        ORDER BY sp.first_seen ASC
      )
      FROM (
        SELECT
          s.agent_id,
          MIN(s.created_at) AS first_seen,
          COALESCE(MAX(a.name), '') AS agent_name
        FROM agent_sessions s
        LEFT JOIN agents a ON a.id = s.agent_id
        WHERE s.table_id = t.id
        GROUP BY s.agent_id
        ORDER BY MIN(s.created_at) ASC
        LIMIT 2
      ) sp
    ),
    '[]'::jsonb
  ) AS participants,
  t.created_at,
  MAX(h.ended_at) AS last_hand_ended_at
FROM tables t
JOIN rooms r ON r.id = t.room_id
LEFT JOIN hands h ON h.table_id = t.id
WHERE (sqlc.arg(room_id)::text = '' OR t.room_id = sqlc.arg(room_id)::text)
  AND (
    sqlc.arg(agent_id)::text = ''
    OR EXISTS (
      SELECT 1
      FROM agent_sessions s
      WHERE s.table_id = t.id AND s.agent_id = sqlc.arg(agent_id)::text
    )
  )
GROUP BY t.id, t.room_id, r.name, t.status, t.small_blind_cc, t.big_blind_cc, t.created_at
ORDER BY MAX(h.started_at) DESC NULLS LAST, t.created_at DESC
LIMIT sqlc.arg(limit_rows) OFFSET sqlc.arg(offset_rows);

-- name: CountTableHistoryByScope :one
SELECT COUNT(*)::bigint
FROM tables t
WHERE (sqlc.arg(room_id)::text = '' OR t.room_id = sqlc.arg(room_id)::text)
  AND (
    sqlc.arg(agent_id)::text = ''
    OR EXISTS (
      SELECT 1
      FROM agent_sessions s
      WHERE s.table_id = t.id AND s.agent_id = sqlc.arg(agent_id)::text
    )
  );
