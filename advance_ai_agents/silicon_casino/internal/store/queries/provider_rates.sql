-- name: RecordProxyCall :exec
INSERT INTO proxy_calls (id, agent_id, prompt_tokens, completion_tokens, total_tokens, model, provider, cost_cc)
VALUES ($1, $2, $3, $4, $5, $6, $7, $8);

-- name: ListProviderRates :many
SELECT provider, price_per_1k_tokens_usd, cc_per_usd, weight, updated_at
FROM provider_rates
ORDER BY provider ASC;

-- name: GetProviderRateByProvider :one
SELECT provider, price_per_1k_tokens_usd, cc_per_usd, weight, updated_at
FROM provider_rates
WHERE provider = $1;

-- name: UpsertProviderRate :exec
INSERT INTO provider_rates (provider, price_per_1k_tokens_usd, cc_per_usd, weight)
VALUES ($1, $2, $3, $4)
ON CONFLICT (provider) DO UPDATE
SET price_per_1k_tokens_usd = EXCLUDED.price_per_1k_tokens_usd,
    cc_per_usd = EXCLUDED.cc_per_usd,
    weight = EXCLUDED.weight,
    updated_at = now();

-- name: EnsureDefaultProviderRate :exec
INSERT INTO provider_rates (provider, price_per_1k_tokens_usd, cc_per_usd, weight)
VALUES ($1, $2, $3, $4)
ON CONFLICT (provider) DO NOTHING;
