package store

import (
	"context"

	"silicon-casino/internal/store/sqlcgen"
)

func (s *Store) RecordProxyCall(ctx context.Context, agentID, model, provider string, prompt, completion, total int, cost int64) (string, error) {
	id := NewID()
	err := s.q.RecordProxyCall(ctx, sqlcgen.RecordProxyCallParams{
		ID:               id,
		AgentID:          agentID,
		PromptTokens:     int32(prompt),
		CompletionTokens: int32(completion),
		TotalTokens:      int4Param(int32(total)),
		Model:            textParam(model),
		Provider:         textParam(provider),
		CostCc:           cost,
	})
	return id, err
}
func (s *Store) ListProviderRates(ctx context.Context) ([]ProviderRate, error) {
	rows, err := s.q.ListProviderRates(ctx)
	if err != nil {
		return nil, err
	}
	out := make([]ProviderRate, 0, len(rows))
	for _, r := range rows {
		out = append(out, ProviderRate{
			Provider:            r.Provider,
			PricePer1KTokensUSD: r.PricePer1kTokensUsd,
			CCPerUSD:            r.CcPerUsd,
			Weight:              r.Weight,
			UpdatedAt:           r.UpdatedAt.Time,
		})
	}
	return out, nil
}
func (s *Store) GetProviderRate(ctx context.Context, provider string) (*ProviderRate, error) {
	r, err := s.q.GetProviderRateByProvider(ctx, provider)
	if err != nil {
		return nil, mapNotFound(err)
	}
	return &ProviderRate{
		Provider:            r.Provider,
		PricePer1KTokensUSD: r.PricePer1kTokensUsd,
		CCPerUSD:            r.CcPerUsd,
		Weight:              r.Weight,
		UpdatedAt:           r.UpdatedAt.Time,
	}, nil
}

func (s *Store) UpsertProviderRate(ctx context.Context, provider string, pricePer1KTokensUSD, ccPerUSD, weight float64) error {
	return s.q.UpsertProviderRate(ctx, sqlcgen.UpsertProviderRateParams{
		Provider:            provider,
		PricePer1kTokensUsd: pricePer1KTokensUSD,
		CcPerUsd:            ccPerUSD,
		Weight:              weight,
	})
}

func (s *Store) EnsureDefaultProviderRates(ctx context.Context, defaults []ProviderRate) error {
	for _, r := range defaults {
		if err := s.q.EnsureDefaultProviderRate(ctx, sqlcgen.EnsureDefaultProviderRateParams{
			Provider:            r.Provider,
			PricePer1kTokensUsd: r.PricePer1KTokensUSD,
			CcPerUsd:            r.CCPerUSD,
			Weight:              r.Weight,
		}); err != nil {
			return err
		}
	}
	return nil
}
