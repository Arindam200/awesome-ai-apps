-- name: InsertLedgerEntry :exec
INSERT INTO ledger_entries (id, agent_id, type, amount_cc, ref_type, ref_id)
VALUES ($1, $2, $3, $4, $5, $6);

-- name: ListLedgerEntries :many
SELECT id, agent_id, type, amount_cc, ref_type, ref_id, created_at
FROM ledger_entries
WHERE ($1::text = '' OR agent_id = $1)
  AND ($2::text = '' OR (ref_type = 'hand' AND ref_id = $2))
  AND ($3::timestamptz IS NULL OR created_at >= $3)
  AND ($4::timestamptz IS NULL OR created_at <= $4)
ORDER BY created_at DESC
LIMIT $5 OFFSET $6;

-- name: ListLeaderboard :many
SELECT a.id, a.name, COALESCE(SUM(l.amount_cc), 0)::bigint AS net_cc
FROM agents a
LEFT JOIN ledger_entries l ON l.agent_id = a.id
GROUP BY a.id, a.name
ORDER BY net_cc DESC
LIMIT $1 OFFSET $2;
