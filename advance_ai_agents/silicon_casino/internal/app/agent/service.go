package agent

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"math"
	"net/http"
	"strconv"
	"strings"
	"time"

	"silicon-casino/internal/config"
	"silicon-casino/internal/store"
)

type Service struct {
	store *store.Store
	cfg   config.ServerConfig
}

const (
	providerOpenRouter = "openrouter"
	providerNebius     = "nebius"
)

var (
	openRouterBaseURL = "https://openrouter.ai/api/v1"
	nebiusBaseURL     = "https://api.studio.nebius.com/v1"
)

func SetVendorBaseURLsForTesting(openrouterURL, nebiusURL string) func() {
	oldOpenRouter := openRouterBaseURL
	oldNebius := nebiusBaseURL
	if strings.TrimSpace(openrouterURL) != "" {
		openRouterBaseURL = openrouterURL
	}
	if strings.TrimSpace(nebiusURL) != "" {
		nebiusBaseURL = nebiusURL
	}
	return func() {
		openRouterBaseURL = oldOpenRouter
		nebiusBaseURL = oldNebius
	}
}

func NewService(st *store.Store, cfg config.ServerConfig) *Service {
	return &Service{store: st, cfg: cfg}
}

func (s *Service) Register(ctx context.Context, in RegisterInput) (*RegisterResponse, error) {
	if strings.TrimSpace(in.Name) == "" {
		return nil, ErrInvalidRequest
	}
	apiKey := "apa_" + strconv.FormatInt(time.Now().UnixNano(), 10)
	claimCode := "apa_claim_" + strconv.FormatInt(time.Now().UnixNano(), 10)
	id, err := s.store.CreateAgent(ctx, in.Name, apiKey, claimCode)
	if err != nil {
		return nil, err
	}
	_ = s.store.EnsureAccount(ctx, id, 10000)

	resp := &RegisterResponse{}
	resp.Agent.AgentID = id
	resp.Agent.APIKey = apiKey
	resp.Agent.ClaimURL = "http://localhost:8080/claim/" + claimCode
	resp.Agent.VerificationCode = claimCode
	return resp, nil
}

func (s *Service) Me(ctx context.Context, agent *store.Agent) (*MeResponse, error) {
	if agent == nil {
		return nil, ErrInvalidRequest
	}
	balance, err := s.store.GetAccountBalance(ctx, agent.ID)
	if err != nil {
		return nil, err
	}
	return &MeResponse{
		AgentID:   agent.ID,
		Name:      agent.Name,
		Status:    agent.Status,
		BalanceCC: balance,
		CreatedAt: agent.CreatedAt,
	}, nil
}

func (s *Service) Claim(ctx context.Context, in ClaimInput) (*ClaimResponse, error) {
	if in.AgentID == "" || in.ClaimCode == "" {
		return nil, ErrInvalidRequest
	}
	claim, err := s.store.GetAgentClaimByAgent(ctx, in.AgentID)
	if err != nil || claim.ClaimCode != in.ClaimCode {
		return nil, ErrInvalidClaim
	}
	if err := s.store.MarkAgentClaimed(ctx, in.AgentID); err != nil {
		return nil, err
	}
	return &ClaimResponse{OK: true}, nil
}

func (s *Service) ClaimByCode(ctx context.Context, claimCode string) (*ClaimByCodeResponse, error) {
	if claimCode == "" {
		return nil, ErrInvalidRequest
	}
	claim, err := s.store.GetAgentClaimByCode(ctx, claimCode)
	if err != nil {
		if errors.Is(err, store.ErrNotFound) {
			return nil, ErrClaimNotFound
		}
		return nil, err
	}
	if claim.Status != "claimed" {
		if err := s.store.MarkAgentClaimed(ctx, claim.AgentID); err != nil {
			return nil, err
		}
		claim.Status = "claimed"
	}
	return &ClaimByCodeResponse{OK: true, AgentID: claim.AgentID, Status: claim.Status}, nil
}

func (s *Service) BindKey(ctx context.Context, agent *store.Agent, in BindKeyInput) (*BindKeyResponse, error) {
	if agent == nil {
		return nil, ErrInvalidRequest
	}
	in.Provider = strings.ToLower(strings.TrimSpace(in.Provider))
	if in.Provider == "" || in.APIKey == "" || in.BudgetUSD <= 0 {
		return nil, ErrInvalidRequest
	}
	if in.BudgetUSD > s.cfg.MaxBudgetUSD {
		return nil, ErrBudgetExceedsLimit
	}
	if !isProviderEnabled(in.Provider) {
		return nil, ErrInvalidProvider
	}

	if blocked, reason, err := s.store.IsAgentBlacklisted(ctx, agent.ID); err != nil {
		return nil, err
	} else if blocked {
		return nil, &BlacklistError{Reason: reason}
	}

	if last, err := s.store.LastSuccessfulKeyBindAt(ctx, agent.ID); err != nil {
		return nil, err
	} else if last != nil {
		cooldown := time.Duration(s.cfg.BindCooldownMins) * time.Minute
		if time.Since(*last) < cooldown {
			return nil, ErrCooldownActive
		}
	}

	keyHash := store.HashAPIKey(in.APIKey)
	if existing, err := s.store.GetAgentKeyByHash(ctx, keyHash); err == nil && existing != nil {
		return nil, ErrAPIKeyAlreadyBound
	} else if err != nil && !errors.Is(err, store.ErrNotFound) {
		return nil, err
	}

	appliedBudgetUSD := in.BudgetUSD
	if !s.cfg.AllowAnyVendorKey {
		availableUSD, err := fetchVendorAvailableUSD(ctx, in.Provider, in.APIKey)
		if err != nil {
			_ = s.store.RecordAgentKeyAttempt(ctx, agent.ID, in.Provider, "invalid_key")
			if n, err := s.store.CountConsecutiveInvalidKeyAttempts(ctx, agent.ID); err == nil && n >= 3 {
				_ = s.store.BlacklistAgent(ctx, agent.ID, "too_many_invalid_keys")
				return nil, &BlacklistError{}
			}
			return nil, err
		}
		appliedBudgetUSD = math.Min(in.BudgetUSD, availableUSD)
		if appliedBudgetUSD <= 0 {
			return nil, ErrInsufficientVendorBalance
		}
	}

	rate, err := s.store.GetProviderRate(ctx, in.Provider)
	if err != nil {
		return nil, ErrInvalidProvider
	}
	credit := store.ComputeCCFromBudgetUSD(appliedBudgetUSD, rate.CCPerUSD, rate.Weight)
	if credit <= 0 {
		return nil, ErrInvalidRequest
	}

	keyID, err := s.store.CreateAgentKey(ctx, agent.ID, in.Provider, keyHash)
	if err != nil {
		return nil, ErrAPIKeyAlreadyBound
	}
	_ = s.store.RecordAgentKeyAttempt(ctx, agent.ID, in.Provider, "success")
	_ = s.store.EnsureAccount(ctx, agent.ID, 0)
	newBal, err := s.store.Credit(ctx, agent.ID, credit, "key_credit", "agent_key", keyID)
	if err != nil {
		return nil, err
	}

	return &BindKeyResponse{OK: true, AddedCC: credit, BalanceCC: newBal}, nil
}

func fetchVendorAvailableUSD(ctx context.Context, provider, apiKey string) (float64, error) {
	baseURL := ""
	path := ""
	switch provider {
	case providerOpenRouter:
		baseURL = openRouterBaseURL
		path = "/key"
	case providerNebius:
		baseURL = nebiusBaseURL
		path = "/credits"
	default:
		return 0, ErrInvalidProvider
	}

	client := &http.Client{Timeout: 10 * time.Second}
	url := strings.TrimRight(baseURL, "/") + path
	for attempt := 0; attempt < 2; attempt++ {
		req, err := http.NewRequestWithContext(ctx, http.MethodGet, url, nil)
		if err != nil {
			return 0, err
		}
		req.Header.Set("Authorization", "Bearer "+apiKey)
		resp, err := client.Do(req)
		if err != nil {
			if attempt == 0 && ctx.Err() == nil {
				time.Sleep(200 * time.Millisecond)
				continue
			}
			return 0, ErrInvalidVendorKey
		}
		body, readErr := io.ReadAll(resp.Body)
		resp.Body.Close()
		if readErr != nil {
			return 0, ErrInvalidVendorKey
		}
		if resp.StatusCode >= 500 && attempt == 0 {
			time.Sleep(200 * time.Millisecond)
			continue
		}
		if resp.StatusCode >= 400 {
			return 0, ErrInvalidVendorKey
		}
		availableUSD, parseErr := parseAvailableUSD(body)
		if parseErr != nil {
			return 0, ErrInvalidVendorKey
		}
		if availableUSD <= 0 {
			return 0, ErrInsufficientVendorBalance
		}
		return availableUSD, nil
	}
	return 0, ErrInvalidVendorKey
}

func parseAvailableUSD(body []byte) (float64, error) {
	var payload map[string]any
	if err := json.Unmarshal(body, &payload); err != nil {
		return 0, err
	}
	if value, ok := floatAtPaths(payload,
		"limit_remaining",
		"data.limit_remaining",
		"available_usd",
		"data.available_usd",
		"balance_usd",
		"data.balance_usd",
		"credits.remaining",
	); ok {
		return value, nil
	}
	return 0, fmt.Errorf("available_usd_not_found")
}

func floatAtPaths(payload map[string]any, paths ...string) (float64, bool) {
	for _, path := range paths {
		if value, ok := floatAtPath(payload, path); ok {
			return value, true
		}
	}
	return 0, false
}

func floatAtPath(payload map[string]any, path string) (float64, bool) {
	parts := strings.Split(path, ".")
	var current any = payload
	for _, part := range parts {
		object, ok := current.(map[string]any)
		if !ok {
			return 0, false
		}
		next, ok := object[part]
		if !ok {
			return 0, false
		}
		current = next
	}
	switch v := current.(type) {
	case float64:
		return v, true
	case int:
		return float64(v), true
	case int64:
		return float64(v), true
	case json.Number:
		f, err := v.Float64()
		if err == nil {
			return f, true
		}
	case string:
		f, err := strconv.ParseFloat(strings.TrimSpace(v), 64)
		if err == nil {
			return f, true
		}
	}
	return 0, false
}

func isProviderEnabled(provider string) bool {
	switch provider {
	case providerOpenRouter, providerNebius:
		return true
	default:
		return false
	}
}
