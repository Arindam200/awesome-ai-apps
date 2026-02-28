package runtime

import (
	"context"

	"silicon-casino/internal/agentgateway/policy"
	"silicon-casino/internal/store"
)

func authenticateAgent(ctx context.Context, st *store.Store, agentID, apiKey string) (*store.Agent, error) {
	return policy.AuthenticateAgent(ctx, st, agentID, apiKey)
}
