package store

import (
	"context"
	"errors"
	"time"

	"silicon-casino/internal/store/sqlcgen"

	"github.com/jackc/pgx/v5"
)

func (s *Store) GetAgentByAPIKey(ctx context.Context, apiKey string) (*Agent, error) {
	hash := HashAPIKey(apiKey)
	row, err := s.q.GetAgentByAPIKeyHash(ctx, hash)
	if err != nil {
		return nil, mapNotFound(err)
	}
	return &Agent{
		ID:         row.ID,
		Name:       row.Name,
		APIKeyHash: row.ApiKeyHash,
		Status:     row.Status,
		ClaimCode:  row.ClaimCode,
		CreatedAt:  row.CreatedAt.Time,
	}, nil
}

func (s *Store) GetAgentByID(ctx context.Context, id string) (*Agent, error) {
	row, err := s.q.GetAgentByID(ctx, id)
	if err != nil {
		return nil, mapNotFound(err)
	}
	return &Agent{
		ID:         row.ID,
		Name:       row.Name,
		APIKeyHash: row.ApiKeyHash,
		Status:     row.Status,
		ClaimCode:  row.ClaimCode,
		CreatedAt:  row.CreatedAt.Time,
	}, nil
}

func (s *Store) CreateAgent(ctx context.Context, name, apiKey, claimCode string) (string, error) {
	id := NewID()
	hash := HashAPIKey(apiKey)
	err := s.q.CreateAgent(ctx, sqlcgen.CreateAgentParams{
		ID:         id,
		Name:       name,
		ApiKeyHash: hash,
		ClaimCode:  claimCode,
	})
	return id, err
}
func (s *Store) ListAgents(ctx context.Context, limit, offset int) ([]Agent, error) {
	if limit <= 0 {
		limit = 50
	}
	rows, err := s.q.ListAgents(ctx, sqlcgen.ListAgentsParams{
		Limit:  int32(limit),
		Offset: int32(offset),
	})
	if err != nil {
		return nil, err
	}
	out := make([]Agent, 0, len(rows))
	for _, r := range rows {
		out = append(out, Agent{
			ID:         r.ID,
			Name:       r.Name,
			APIKeyHash: r.ApiKeyHash,
			Status:     r.Status,
			ClaimCode:  r.ClaimCode,
			CreatedAt:  r.CreatedAt.Time,
		})
	}
	return out, nil
}

func (s *Store) GetAgentClaimByAgent(ctx context.Context, agentID string) (*AgentClaim, error) {
	r, err := s.q.GetAgentClaimByAgentID(ctx, agentID)
	if err != nil {
		return nil, mapNotFound(err)
	}
	return &AgentClaim{
		ID:        r.ID,
		AgentID:   r.AgentID,
		ClaimCode: r.ClaimCode,
		Status:    r.Status,
		CreatedAt: r.CreatedAt.Time,
	}, nil
}

func (s *Store) GetAgentClaimByCode(ctx context.Context, claimCode string) (*AgentClaim, error) {
	r, err := s.q.GetAgentClaimByClaimCode(ctx, claimCode)
	if err != nil {
		return nil, mapNotFound(err)
	}
	return &AgentClaim{
		ID:        r.ID,
		AgentID:   r.AgentID,
		ClaimCode: r.ClaimCode,
		Status:    r.Status,
		CreatedAt: r.CreatedAt.Time,
	}, nil
}

func (s *Store) MarkAgentClaimed(ctx context.Context, agentID string) error {
	return s.q.MarkAgentStatusClaimed(ctx, agentID)
}

func (s *Store) CreateAgentKey(ctx context.Context, agentID, provider, apiKeyHash string) (string, error) {
	id := NewID()
	err := s.q.CreateAgentKey(ctx, sqlcgen.CreateAgentKeyParams{
		ID:         id,
		AgentID:    agentID,
		Provider:   provider,
		ApiKeyHash: apiKeyHash,
	})
	return id, err
}

func (s *Store) GetAgentKeyByHash(ctx context.Context, apiKeyHash string) (*AgentKey, error) {
	r, err := s.q.GetAgentKeyByAPIKeyHash(ctx, apiKeyHash)
	if err != nil {
		return nil, mapNotFound(err)
	}
	return &AgentKey{
		ID:         r.ID,
		AgentID:    r.AgentID,
		Provider:   r.Provider,
		APIKeyHash: r.ApiKeyHash,
		Status:     r.Status,
		CreatedAt:  r.CreatedAt.Time,
	}, nil
}
func (s *Store) IsAgentBlacklisted(ctx context.Context, agentID string) (bool, string, error) {
	reason, err := s.q.GetAgentBlacklistReasonByAgentID(ctx, agentID)
	if err != nil {
		if errors.Is(err, pgx.ErrNoRows) {
			return false, "", nil
		}
		return false, "", err
	}
	return true, reason, nil
}

func (s *Store) BlacklistAgent(ctx context.Context, agentID, reason string) error {
	return s.q.BlacklistAgent(ctx, sqlcgen.BlacklistAgentParams{AgentID: agentID, Reason: reason})
}

func (s *Store) RecordAgentKeyAttempt(ctx context.Context, agentID, provider, status string) error {
	return s.q.RecordAgentKeyAttempt(ctx, sqlcgen.RecordAgentKeyAttemptParams{
		ID:       NewID(),
		AgentID:  agentID,
		Provider: provider,
		Status:   status,
	})
}

func (s *Store) LastSuccessfulKeyBindAt(ctx context.Context, agentID string) (*time.Time, error) {
	ts, err := s.q.GetLastSuccessfulKeyBindAtByAgentID(ctx, agentID)
	if err != nil {
		if errors.Is(err, pgx.ErrNoRows) {
			return nil, nil
		}
		return nil, err
	}
	if !ts.Valid {
		return nil, nil
	}
	t := ts.Time
	return &t, nil
}

func (s *Store) CountConsecutiveInvalidKeyAttempts(ctx context.Context, agentID string) (int, error) {
	statuses, err := s.q.ListAgentKeyAttemptStatusesByAgentID(ctx, agentID)
	if err != nil {
		return 0, err
	}
	count := 0
	for _, status := range statuses {
		if status == "success" {
			break
		}
		if status == "invalid_key" {
			count++
		}
	}
	return count, nil
}
