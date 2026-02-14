package policy

import (
	"context"
	"errors"

	"silicon-casino/internal/store"
)

func AuthenticateAgent(ctx context.Context, st *store.Store, agentID, apiKey string) (*store.Agent, error) {
	if agentID == "" || apiKey == "" {
		return nil, errors.New("invalid_api_key")
	}
	agent, err := st.GetAgentByAPIKey(ctx, apiKey)
	if err != nil || agent == nil || agent.ID != agentID {
		return nil, errors.New("invalid_api_key")
	}
	return agent, nil
}
