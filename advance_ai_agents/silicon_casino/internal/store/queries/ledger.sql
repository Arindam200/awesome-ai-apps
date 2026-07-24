-- name: InsertLedgerEntry :exec
INSERT INTO ledger_entries (id, agent_id, type, amount_cc, ref_type, ref_id)
VALUES ($1, $2, $3, $4, $5, $6);

-- name: ListLedgerEntries :many
SELECT id, agent_id, type, amount_cc, ref_type, ref_id, created_at
FROM ledger_entries
WHERE (sqlc.arg(agent_id)::text = '' OR agent_id = sqlc.arg(agent_id)::text)
  AND (sqlc.arg(hand_id)::text = '' OR (ref_type = 'hand' AND ref_id = sqlc.arg(hand_id)::text))
  AND (sqlc.arg(from_ts)::timestamptz IS NULL OR created_at >= sqlc.arg(from_ts)::timestamptz)
  AND (sqlc.arg(to_ts)::timestamptz IS NULL OR created_at <= sqlc.arg(to_ts)::timestamptz)
ORDER BY created_at DESC
LIMIT sqlc.arg(limit_rows) OFFSET sqlc.arg(offset_rows);

-- name: ListLeaderboard :many
WITH hand_ledger AS (
  SELECT
    l.agent_id,
    l.ref_id AS hand_id,
    SUM(l.amount_cc)::bigint AS hand_net_cc
  FROM ledger_entries l
  WHERE l.ref_type = 'hand'
    AND l.type IN ('blind_debit', 'bet_debit', 'pot_credit')
  GROUP BY l.agent_id, l.ref_id
),
scoped_hand_ledger AS (
  SELECT
    hl.agent_id,
    hl.hand_id,
    hl.hand_net_cc,
    h.winner_agent_id,
    h.ended_at,
    t.big_blind_cc
  FROM hand_ledger hl
  JOIN hands h ON h.id = hl.hand_id
  JOIN tables t ON t.id = h.table_id
  JOIN rooms r ON r.id = t.room_id
  WHERE h.ended_at IS NOT NULL
    AND (sqlc.arg(window_start)::timestamptz IS NULL OR h.ended_at >= sqlc.arg(window_start)::timestamptz)
    AND (sqlc.arg(room_scope)::text = 'all' OR lower(r.name) = sqlc.arg(room_scope)::text)
),
aggregated AS (
  SELECT
    shl.agent_id,
    COUNT(*)::int AS hands_played,
    SUM(CASE WHEN shl.winner_agent_id = shl.agent_id THEN 1 ELSE 0 END)::int AS wins,
    SUM(shl.hand_net_cc)::bigint AS net_cc_from_play,
    SUM(shl.hand_net_cc::numeric / NULLIF(shl.big_blind_cc::numeric, 0)) AS net_bb,
    MAX(shl.ended_at) AS last_active_at
  FROM scoped_hand_ledger shl
  GROUP BY shl.agent_id
)
SELECT
  a.id AS agent_id,
  a.name,
  COALESCE((agg.net_bb / agg.hands_played::numeric) * 100, 0)::numeric AS bb_per_100,
  agg.net_cc_from_play,
  agg.hands_played,
  COALESCE(agg.wins::numeric / NULLIF(agg.hands_played::numeric, 0), 0)::numeric AS win_rate,
  COALESCE(LEAST(1.0::numeric, agg.hands_played::numeric / 500.0), 0)::numeric AS confidence_factor,
  (
    COALESCE((agg.net_bb / agg.hands_played::numeric) * 100, 0)::numeric *
    COALESCE(LEAST(1.0::numeric, agg.hands_played::numeric / 500.0), 0)::numeric
  )::numeric AS score,
  agg.last_active_at
FROM aggregated agg
JOIN agents a ON a.id = agg.agent_id
ORDER BY
  CASE WHEN sqlc.arg(sort_by)::text = 'score' THEN (
    COALESCE((agg.net_bb / agg.hands_played::numeric) * 100, 0)::numeric *
    COALESCE(LEAST(1.0::numeric, agg.hands_played::numeric / 500.0), 0)::numeric
  ) END DESC,
  CASE WHEN sqlc.arg(sort_by)::text = 'net_cc_from_play' THEN agg.net_cc_from_play::numeric END DESC,
  CASE WHEN sqlc.arg(sort_by)::text = 'hands_played' THEN agg.hands_played::numeric END DESC,
  CASE WHEN sqlc.arg(sort_by)::text = 'win_rate' THEN COALESCE(agg.wins::numeric / NULLIF(agg.hands_played::numeric, 0), 0)::numeric END DESC,
  agg.hands_played DESC,
  agg.last_active_at DESC,
  a.id ASC
LIMIT sqlc.arg(limit_rows) OFFSET sqlc.arg(offset_rows);

-- name: GetAgentPerformanceByWindowAndAgent :one
WITH hand_ledger AS (
  SELECT
    l.agent_id,
    l.ref_id AS hand_id,
    SUM(l.amount_cc)::bigint AS hand_net_cc
  FROM ledger_entries l
  WHERE l.ref_type = 'hand'
    AND l.type IN ('blind_debit', 'bet_debit', 'pot_credit')
    AND l.agent_id = sqlc.arg(agent_id)::text
  GROUP BY l.agent_id, l.ref_id
),
scoped_hand_ledger AS (
  SELECT
    hl.agent_id,
    hl.hand_id,
    hl.hand_net_cc,
    h.winner_agent_id,
    h.ended_at,
    t.big_blind_cc
  FROM hand_ledger hl
  JOIN hands h ON h.id = hl.hand_id
  JOIN tables t ON t.id = h.table_id
  WHERE h.ended_at IS NOT NULL
    AND (sqlc.arg(window_start)::timestamptz IS NULL OR h.ended_at >= sqlc.arg(window_start)::timestamptz)
),
aggregated AS (
  SELECT
    shl.agent_id,
    COUNT(*)::int AS hands_played,
    SUM(CASE WHEN shl.winner_agent_id = shl.agent_id THEN 1 ELSE 0 END)::int AS wins,
    SUM(shl.hand_net_cc)::bigint AS net_cc_from_play,
    SUM(shl.hand_net_cc::numeric / NULLIF(shl.big_blind_cc::numeric, 0)) AS net_bb,
    MAX(shl.ended_at) AS last_active_at
  FROM scoped_hand_ledger shl
  GROUP BY shl.agent_id
)
SELECT
  a.id AS agent_id,
  COALESCE((agg.net_bb / NULLIF(agg.hands_played::numeric, 0)) * 100, 0)::numeric AS bb_per_100,
  COALESCE(agg.net_cc_from_play, 0)::bigint AS net_cc_from_play,
  COALESCE(agg.hands_played, 0)::int AS hands_played,
  COALESCE(agg.wins::numeric / NULLIF(agg.hands_played::numeric, 0), 0)::numeric AS win_rate,
  COALESCE(LEAST(1.0::numeric, COALESCE(agg.hands_played, 0)::numeric / 500.0), 0)::numeric AS confidence_factor,
  (
    COALESCE((agg.net_bb / NULLIF(agg.hands_played::numeric, 0)) * 100, 0)::numeric *
    COALESCE(LEAST(1.0::numeric, COALESCE(agg.hands_played, 0)::numeric / 500.0), 0)::numeric
  )::numeric AS score,
  agg.last_active_at
FROM agents a
LEFT JOIN aggregated agg ON agg.agent_id = a.id
WHERE a.id = sqlc.arg(agent_id)::text
LIMIT 1;
