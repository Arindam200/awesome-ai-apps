-- name: EnsureAccount :exec
UPDATE agents
SET balance_cc = $2, updated_at = now()
WHERE id = $1 AND balance_cc = 0;

-- name: GetAccountBalanceByAgentID :one
SELECT balance_cc
FROM agents
WHERE id = $1;

-- name: GetAccountBalanceByAgentIDForUpdate :one
SELECT balance_cc
FROM agents
WHERE id = $1
FOR UPDATE;

-- name: UpdateAccountBalance :exec
UPDATE agents
SET balance_cc = $1, updated_at = now()
WHERE id = $2;

-- name: ListAccounts :many
SELECT id AS agent_id, balance_cc, updated_at
FROM agents
WHERE ($1::text = '' OR id = $1)
ORDER BY updated_at DESC
LIMIT $2 OFFSET $3;
