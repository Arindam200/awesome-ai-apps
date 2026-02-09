package main

import (
	"bytes"
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"silicon-casino/internal/config"
	"silicon-casino/internal/store"
	"silicon-casino/internal/testutil"
)

func TestBindKeyHandler_Success(t *testing.T) {
	st, cleanup := testutil.OpenTestStore(t)
	defer cleanup()

	ctx := context.Background()
	if err := st.UpsertProviderRate(ctx, "openai", 0.0001, 1000, 1); err != nil {
		t.Fatalf("upsert provider rate: %v", err)
	}

	apiKey := "apa_key_a"
	agentID, err := st.CreateAgent(ctx, "AgentA", apiKey, "claim-"+apiKey)
	if err != nil {
		t.Fatalf("create agent: %v", err)
	}
	if err := st.EnsureAccount(ctx, agentID, 0); err != nil {
		t.Fatalf("ensure account: %v", err)
	}

	body := []byte(`{"provider":"openai","api_key":"sk-test","budget_usd":10}`)
	req := httptest.NewRequest(http.MethodPost, "/api/agents/bind_key", bytes.NewReader(body))
	req.Header.Set("Authorization", "Bearer "+apiKey)
	rr := httptest.NewRecorder()

	bindKeyHandler(st, testServerConfig(http.StatusOK, t)).ServeHTTP(rr, req)
	if rr.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d: %s", rr.Code, rr.Body.String())
	}

	var resp struct {
		AddedCC   int64 `json:"added_cc"`
		BalanceCC int64 `json:"balance_cc"`
	}
	if err := json.NewDecoder(rr.Body).Decode(&resp); err != nil {
		t.Fatalf("decode response: %v", err)
	}
	if resp.AddedCC != 10000 {
		t.Fatalf("expected added_cc 10000, got %d", resp.AddedCC)
	}
	if resp.BalanceCC != 10000 {
		t.Fatalf("expected balance_cc 10000, got %d", resp.BalanceCC)
	}

	hash := store.HashAPIKey("sk-test")
	key, err := st.GetAgentKeyByHash(ctx, hash)
	if err != nil {
		t.Fatalf("get agent key: %v", err)
	}
	if key.AgentID != agentID {
		t.Fatalf("expected agent_id %s, got %s", agentID, key.AgentID)
	}
}

func TestBindKeyHandler_DuplicateKey(t *testing.T) {
	st, cleanup := testutil.OpenTestStore(t)
	defer cleanup()

	ctx := context.Background()
	if err := st.UpsertProviderRate(ctx, "openai", 0.0001, 1000, 1); err != nil {
		t.Fatalf("upsert provider rate: %v", err)
	}

	apiKey1 := "apa_key_a"
	agentID1, err := st.CreateAgent(ctx, "AgentA", apiKey1, "claim-"+apiKey1)
	if err != nil {
		t.Fatalf("create agent: %v", err)
	}
	if err := st.EnsureAccount(ctx, agentID1, 0); err != nil {
		t.Fatalf("ensure account: %v", err)
	}

	body := []byte(`{"provider":"openai","api_key":"sk-test","budget_usd":10}`)
	req := httptest.NewRequest(http.MethodPost, "/api/agents/bind_key", bytes.NewReader(body))
	req.Header.Set("Authorization", "Bearer "+apiKey1)
	rr := httptest.NewRecorder()
	bindKeyHandler(st, testServerConfig(http.StatusOK, t)).ServeHTTP(rr, req)
	if rr.Code != http.StatusOK {
		t.Fatalf("expected first bind 200, got %d", rr.Code)
	}

	apiKey2 := "apa_key_b"
	agentID2, err := st.CreateAgent(ctx, "AgentB", apiKey2, "claim-"+apiKey2)
	if err != nil {
		t.Fatalf("create agent: %v", err)
	}
	if err := st.EnsureAccount(ctx, agentID2, 0); err != nil {
		t.Fatalf("ensure account: %v", err)
	}

	req2 := httptest.NewRequest(http.MethodPost, "/api/agents/bind_key", bytes.NewReader(body))
	req2.Header.Set("Authorization", "Bearer "+apiKey2)
	rr2 := httptest.NewRecorder()
	bindKeyHandler(st, testServerConfig(http.StatusOK, t)).ServeHTTP(rr2, req2)
	if rr2.Code != http.StatusConflict {
		t.Fatalf("expected 409, got %d: %s", rr2.Code, rr2.Body.String())
	}
}

func TestBindKeyHandler_BudgetLimit(t *testing.T) {
	st, cleanup := testutil.OpenTestStore(t)
	defer cleanup()

	ctx := context.Background()
	if err := st.UpsertProviderRate(ctx, "openai", 0.0001, 1000, 1); err != nil {
		t.Fatalf("upsert provider rate: %v", err)
	}

	apiKey := "apa_key_limit"
	agentID, err := st.CreateAgent(ctx, "AgentLimit", apiKey, "claim-"+apiKey)
	if err != nil {
		t.Fatalf("create agent: %v", err)
	}
	if err := st.EnsureAccount(ctx, agentID, 0); err != nil {
		t.Fatalf("ensure account: %v", err)
	}

	body := []byte(`{"provider":"openai","api_key":"sk-test","budget_usd":21}`)
	req := httptest.NewRequest(http.MethodPost, "/api/agents/bind_key", bytes.NewReader(body))
	req.Header.Set("Authorization", "Bearer "+apiKey)
	rr := httptest.NewRecorder()

	bindKeyHandler(st, testServerConfig(http.StatusOK, t)).ServeHTTP(rr, req)
	if rr.Code != http.StatusBadRequest {
		t.Fatalf("expected 400, got %d: %s", rr.Code, rr.Body.String())
	}
}

func TestBindKeyHandler_Cooldown(t *testing.T) {
	st, cleanup := testutil.OpenTestStore(t)
	defer cleanup()

	ctx := context.Background()
	if err := st.UpsertProviderRate(ctx, "openai", 0.0001, 1000, 1); err != nil {
		t.Fatalf("upsert provider rate: %v", err)
	}

	apiKey := "apa_key_cooldown"
	agentID, err := st.CreateAgent(ctx, "AgentCooldown", apiKey, "claim-"+apiKey)
	if err != nil {
		t.Fatalf("create agent: %v", err)
	}
	if err := st.EnsureAccount(ctx, agentID, 0); err != nil {
		t.Fatalf("ensure account: %v", err)
	}

	body1 := []byte(`{"provider":"openai","api_key":"sk-test-1","budget_usd":10}`)
	req1 := httptest.NewRequest(http.MethodPost, "/api/agents/bind_key", bytes.NewReader(body1))
	req1.Header.Set("Authorization", "Bearer "+apiKey)
	rr1 := httptest.NewRecorder()
	bindKeyHandler(st, testServerConfig(http.StatusOK, t)).ServeHTTP(rr1, req1)
	if rr1.Code != http.StatusOK {
		t.Fatalf("expected first bind 200, got %d: %s", rr1.Code, rr1.Body.String())
	}

	body2 := []byte(`{"provider":"openai","api_key":"sk-test-2","budget_usd":10}`)
	req2 := httptest.NewRequest(http.MethodPost, "/api/agents/bind_key", bytes.NewReader(body2))
	req2.Header.Set("Authorization", "Bearer "+apiKey)
	rr2 := httptest.NewRecorder()
	bindKeyHandler(st, testServerConfig(http.StatusOK, t)).ServeHTTP(rr2, req2)
	if rr2.Code != http.StatusTooManyRequests {
		t.Fatalf("expected 429, got %d: %s", rr2.Code, rr2.Body.String())
	}
}

func TestBindKeyHandler_BlacklistAfterInvalidKeys(t *testing.T) {
	st, cleanup := testutil.OpenTestStore(t)
	defer cleanup()

	ctx := context.Background()
	if err := st.UpsertProviderRate(ctx, "openai", 0.0001, 1000, 1); err != nil {
		t.Fatalf("upsert provider rate: %v", err)
	}

	apiKey := "apa_key_block"
	agentID, err := st.CreateAgent(ctx, "AgentBlock", apiKey, "claim-"+apiKey)
	if err != nil {
		t.Fatalf("create agent: %v", err)
	}
	if err := st.EnsureAccount(ctx, agentID, 0); err != nil {
		t.Fatalf("ensure account: %v", err)
	}

	body := []byte(`{"provider":"openai","api_key":"sk-bad","budget_usd":10}`)
	for i := 0; i < 3; i++ {
		req := httptest.NewRequest(http.MethodPost, "/api/agents/bind_key", bytes.NewReader(body))
		req.Header.Set("Authorization", "Bearer "+apiKey)
		rr := httptest.NewRecorder()
		bindKeyHandler(st, testServerConfig(http.StatusUnauthorized, t)).ServeHTTP(rr, req)
		if i < 2 && rr.Code != http.StatusUnauthorized {
			t.Fatalf("expected 401, got %d: %s", rr.Code, rr.Body.String())
		}
		if i == 2 && rr.Code != http.StatusForbidden {
			t.Fatalf("expected 403, got %d: %s", rr.Code, rr.Body.String())
		}
	}

	blocked, _, err := st.IsAgentBlacklisted(ctx, agentID)
	if err != nil {
		t.Fatalf("check blacklist: %v", err)
	}
	if !blocked {
		t.Fatalf("expected agent to be blacklisted after 3 invalid keys")
	}
}

func TestAgentMeHandler(t *testing.T) {
	st, cleanup := testutil.OpenTestStore(t)
	defer cleanup()

	ctx := context.Background()
	apiKey := "apa_key_me"
	agentID, err := st.CreateAgent(ctx, "AgentMe", apiKey, "claim-"+apiKey)
	if err != nil {
		t.Fatalf("create agent: %v", err)
	}

	req := httptest.NewRequest(http.MethodGet, "/api/agents/me", nil)
	req.Header.Set("Authorization", "Bearer "+apiKey)
	rr := httptest.NewRecorder()

	withAgentAuth(st, agentMeHandler(st)).ServeHTTP(rr, req)
	if rr.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d: %s", rr.Code, rr.Body.String())
	}

	var resp struct {
		AgentID string `json:"agent_id"`
		Name    string `json:"name"`
		Status  string `json:"status"`
	}
	if err := json.NewDecoder(rr.Body).Decode(&resp); err != nil {
		t.Fatalf("decode response: %v", err)
	}
	if resp.AgentID != agentID {
		t.Fatalf("expected agent_id %s, got %s", agentID, resp.AgentID)
	}
	if resp.Name != "AgentMe" {
		t.Fatalf("expected name AgentMe, got %s", resp.Name)
	}
	if resp.Status == "" {
		t.Fatalf("expected status to be set")
	}
}

func TestAgentMeHandler_Unauthorized(t *testing.T) {
	st, cleanup := testutil.OpenTestStore(t)
	defer cleanup()

	req := httptest.NewRequest(http.MethodGet, "/api/agents/me", nil)
	rr := httptest.NewRecorder()

	withAgentAuth(st, agentMeHandler(st)).ServeHTTP(rr, req)
	if rr.Code != http.StatusUnauthorized {
		t.Fatalf("expected 401, got %d: %s", rr.Code, rr.Body.String())
	}
}

func mockVendorServer(t *testing.T, status int) string {
	t.Helper()
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/models" {
			w.WriteHeader(http.StatusNotFound)
			return
		}
		w.WriteHeader(status)
	}))
	t.Cleanup(srv.Close)
	return srv.URL
}

func testServerConfig(status int, t *testing.T) config.ServerConfig {
	return config.ServerConfig{
		MaxBudgetUSD:     20,
		BindCooldownMins: 60,
		OpenAIBaseURL:    mockVendorServer(t, status),
		KimiBaseURL:      mockVendorServer(t, status),
	}
}
