package main

import (
	"bytes"
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	appagent "silicon-casino/internal/app/agent"
	"silicon-casino/internal/config"
	"silicon-casino/internal/testutil"
)

func TestBindKeyHandler_OpenAIProviderInvalid(t *testing.T) {
	st, cleanup := testutil.OpenTestStore(t)
	defer cleanup()
	router := newTestRouter(st, testServerConfig())

	ctx := context.Background()
	apiKey := "apa_key_openai_disabled"
	agentID, err := st.CreateAgent(ctx, "AgentOpenAI", apiKey, "claim-"+apiKey)
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

	router.ServeHTTP(rr, req)
	if rr.Code != http.StatusBadRequest {
		t.Fatalf("expected 400, got %d: %s", rr.Code, rr.Body.String())
	}
}

func TestBindKeyHandler_KimiProviderInvalid(t *testing.T) {
	st, cleanup := testutil.OpenTestStore(t)
	defer cleanup()
	router := newTestRouter(st, testServerConfig())

	ctx := context.Background()
	apiKey := "apa_key_kimi_disabled"
	agentID, err := st.CreateAgent(ctx, "AgentKimi", apiKey, "claim-"+apiKey)
	if err != nil {
		t.Fatalf("create agent: %v", err)
	}
	if err := st.EnsureAccount(ctx, agentID, 0); err != nil {
		t.Fatalf("ensure account: %v", err)
	}

	body := []byte(`{"provider":"kimi","api_key":"kimi-test","budget_usd":10}`)
	req := httptest.NewRequest(http.MethodPost, "/api/agents/bind_key", bytes.NewReader(body))
	req.Header.Set("Authorization", "Bearer "+apiKey)
	rr := httptest.NewRecorder()

	router.ServeHTTP(rr, req)
	if rr.Code != http.StatusBadRequest {
		t.Fatalf("expected 400, got %d: %s", rr.Code, rr.Body.String())
	}
}

func TestBindKeyHandler_OpenRouterPartialTopup(t *testing.T) {
	st, cleanup := testutil.OpenTestStore(t)
	defer cleanup()
	provider := mockProviderServer(t, providerMockConfig{openRouterStatus: http.StatusOK, openRouterBody: `{"data":{"limit_remaining":3.5}}`})
	restore := appagent.SetVendorBaseURLsForTesting(provider.URL, provider.URL)
	t.Cleanup(restore)
	router := newTestRouter(st, testServerConfig())

	ctx := context.Background()
	if err := st.UpsertProviderRate(ctx, "openrouter", 0.0001, 1000, 1); err != nil {
		t.Fatalf("upsert provider rate: %v", err)
	}

	apiKey := "apa_key_or_partial"
	agentID, err := st.CreateAgent(ctx, "AgentOpenRouter", apiKey, "claim-"+apiKey)
	if err != nil {
		t.Fatalf("create agent: %v", err)
	}
	if err := st.EnsureAccount(ctx, agentID, 0); err != nil {
		t.Fatalf("ensure account: %v", err)
	}

	body := []byte(`{"provider":"openrouter","api_key":"or-test","budget_usd":10}`)
	req := httptest.NewRequest(http.MethodPost, "/api/agents/bind_key", bytes.NewReader(body))
	req.Header.Set("Authorization", "Bearer "+apiKey)
	rr := httptest.NewRecorder()

	router.ServeHTTP(rr, req)
	if rr.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d: %s", rr.Code, rr.Body.String())
	}

	var resp struct {
		AddedCC int64 `json:"added_cc"`
	}
	if err := json.NewDecoder(rr.Body).Decode(&resp); err != nil {
		t.Fatalf("decode response: %v", err)
	}
	if resp.AddedCC != 3500 {
		t.Fatalf("expected partial topup 3500, got %d", resp.AddedCC)
	}
}

func TestBindKeyHandler_OpenRouterFullTopup(t *testing.T) {
	st, cleanup := testutil.OpenTestStore(t)
	defer cleanup()
	provider := mockProviderServer(t, providerMockConfig{openRouterStatus: http.StatusOK, openRouterBody: `{"limit_remaining":25}`})
	restore := appagent.SetVendorBaseURLsForTesting(provider.URL, provider.URL)
	t.Cleanup(restore)
	router := newTestRouter(st, testServerConfig())

	ctx := context.Background()
	if err := st.UpsertProviderRate(ctx, "openrouter", 0.0001, 1000, 1); err != nil {
		t.Fatalf("upsert provider rate: %v", err)
	}

	apiKey := "apa_key_or_full"
	agentID, err := st.CreateAgent(ctx, "AgentOpenRouterFull", apiKey, "claim-"+apiKey)
	if err != nil {
		t.Fatalf("create agent: %v", err)
	}
	if err := st.EnsureAccount(ctx, agentID, 0); err != nil {
		t.Fatalf("ensure account: %v", err)
	}

	body := []byte(`{"provider":"openrouter","api_key":"or-test","budget_usd":10}`)
	req := httptest.NewRequest(http.MethodPost, "/api/agents/bind_key", bytes.NewReader(body))
	req.Header.Set("Authorization", "Bearer "+apiKey)
	rr := httptest.NewRecorder()

	router.ServeHTTP(rr, req)
	if rr.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d: %s", rr.Code, rr.Body.String())
	}

	var resp struct {
		AddedCC int64 `json:"added_cc"`
	}
	if err := json.NewDecoder(rr.Body).Decode(&resp); err != nil {
		t.Fatalf("decode response: %v", err)
	}
	if resp.AddedCC != 10000 {
		t.Fatalf("expected full topup 10000, got %d", resp.AddedCC)
	}
}

func TestBindKeyHandler_OpenRouterInsufficientVendorBalance(t *testing.T) {
	st, cleanup := testutil.OpenTestStore(t)
	defer cleanup()
	provider := mockProviderServer(t, providerMockConfig{openRouterStatus: http.StatusOK, openRouterBody: `{"data":{"limit_remaining":0}}`})
	restore := appagent.SetVendorBaseURLsForTesting(provider.URL, provider.URL)
	t.Cleanup(restore)
	router := newTestRouter(st, testServerConfig())

	ctx := context.Background()
	if err := st.UpsertProviderRate(ctx, "openrouter", 0.0001, 1000, 1); err != nil {
		t.Fatalf("upsert provider rate: %v", err)
	}

	apiKey := "apa_key_or_empty"
	agentID, err := st.CreateAgent(ctx, "AgentOpenRouterEmpty", apiKey, "claim-"+apiKey)
	if err != nil {
		t.Fatalf("create agent: %v", err)
	}
	if err := st.EnsureAccount(ctx, agentID, 0); err != nil {
		t.Fatalf("ensure account: %v", err)
	}

	body := []byte(`{"provider":"openrouter","api_key":"or-empty","budget_usd":10}`)
	req := httptest.NewRequest(http.MethodPost, "/api/agents/bind_key", bytes.NewReader(body))
	req.Header.Set("Authorization", "Bearer "+apiKey)
	rr := httptest.NewRecorder()

	router.ServeHTTP(rr, req)
	if rr.Code != http.StatusBadRequest {
		t.Fatalf("expected 400, got %d: %s", rr.Code, rr.Body.String())
	}
	if !bytes.Contains(rr.Body.Bytes(), []byte("insufficient_vendor_balance")) {
		t.Fatalf("expected insufficient_vendor_balance, got: %s", rr.Body.String())
	}
}

func TestBindKeyHandler_OpenRouterInvalidKeyBlacklist(t *testing.T) {
	st, cleanup := testutil.OpenTestStore(t)
	defer cleanup()
	provider := mockProviderServer(t, providerMockConfig{openRouterStatus: http.StatusUnauthorized})
	restore := appagent.SetVendorBaseURLsForTesting(provider.URL, provider.URL)
	t.Cleanup(restore)
	router := newTestRouter(st, testServerConfig())

	ctx := context.Background()
	if err := st.UpsertProviderRate(ctx, "openrouter", 0.0001, 1000, 1); err != nil {
		t.Fatalf("upsert provider rate: %v", err)
	}

	apiKey := "apa_key_or_bad"
	agentID, err := st.CreateAgent(ctx, "AgentOpenRouterBad", apiKey, "claim-"+apiKey)
	if err != nil {
		t.Fatalf("create agent: %v", err)
	}
	if err := st.EnsureAccount(ctx, agentID, 0); err != nil {
		t.Fatalf("ensure account: %v", err)
	}

	body := []byte(`{"provider":"openrouter","api_key":"or-bad","budget_usd":10}`)
	for i := 0; i < 3; i++ {
		req := httptest.NewRequest(http.MethodPost, "/api/agents/bind_key", bytes.NewReader(body))
		req.Header.Set("Authorization", "Bearer "+apiKey)
		rr := httptest.NewRecorder()
		router.ServeHTTP(rr, req)
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

func TestBindKeyHandler_NebiusPartialTopup(t *testing.T) {
	st, cleanup := testutil.OpenTestStore(t)
	defer cleanup()
	provider := mockProviderServer(t, providerMockConfig{nebiusStatus: http.StatusOK, nebiusBody: `{"available_usd":4.2}`})
	restore := appagent.SetVendorBaseURLsForTesting(provider.URL, provider.URL)
	t.Cleanup(restore)
	router := newTestRouter(st, testServerConfig())

	ctx := context.Background()
	if err := st.UpsertProviderRate(ctx, "nebius", 0.0001, 1000, 1); err != nil {
		t.Fatalf("upsert provider rate: %v", err)
	}

	apiKey := "apa_key_nb_partial"
	agentID, err := st.CreateAgent(ctx, "AgentNebiusPartial", apiKey, "claim-"+apiKey)
	if err != nil {
		t.Fatalf("create agent: %v", err)
	}
	if err := st.EnsureAccount(ctx, agentID, 0); err != nil {
		t.Fatalf("ensure account: %v", err)
	}

	body := []byte(`{"provider":"nebius","api_key":"nb-test","budget_usd":10}`)
	req := httptest.NewRequest(http.MethodPost, "/api/agents/bind_key", bytes.NewReader(body))
	req.Header.Set("Authorization", "Bearer "+apiKey)
	rr := httptest.NewRecorder()

	router.ServeHTTP(rr, req)
	if rr.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d: %s", rr.Code, rr.Body.String())
	}

	var resp struct {
		AddedCC int64 `json:"added_cc"`
	}
	if err := json.NewDecoder(rr.Body).Decode(&resp); err != nil {
		t.Fatalf("decode response: %v", err)
	}
	if resp.AddedCC != 4200 {
		t.Fatalf("expected partial topup 4200, got %d", resp.AddedCC)
	}
}

func TestBindKeyHandler_NebiusInsufficientVendorBalance(t *testing.T) {
	st, cleanup := testutil.OpenTestStore(t)
	defer cleanup()
	provider := mockProviderServer(t, providerMockConfig{nebiusStatus: http.StatusOK, nebiusBody: `{"available_usd":0}`})
	restore := appagent.SetVendorBaseURLsForTesting(provider.URL, provider.URL)
	t.Cleanup(restore)
	router := newTestRouter(st, testServerConfig())

	ctx := context.Background()
	if err := st.UpsertProviderRate(ctx, "nebius", 0.0001, 1000, 1); err != nil {
		t.Fatalf("upsert provider rate: %v", err)
	}

	apiKey := "apa_key_nb_empty"
	agentID, err := st.CreateAgent(ctx, "AgentNebiusEmpty", apiKey, "claim-"+apiKey)
	if err != nil {
		t.Fatalf("create agent: %v", err)
	}
	if err := st.EnsureAccount(ctx, agentID, 0); err != nil {
		t.Fatalf("ensure account: %v", err)
	}

	body := []byte(`{"provider":"nebius","api_key":"nb-empty","budget_usd":10}`)
	req := httptest.NewRequest(http.MethodPost, "/api/agents/bind_key", bytes.NewReader(body))
	req.Header.Set("Authorization", "Bearer "+apiKey)
	rr := httptest.NewRecorder()

	router.ServeHTTP(rr, req)
	if rr.Code != http.StatusBadRequest {
		t.Fatalf("expected 400, got %d: %s", rr.Code, rr.Body.String())
	}
	if !bytes.Contains(rr.Body.Bytes(), []byte("insufficient_vendor_balance")) {
		t.Fatalf("expected insufficient_vendor_balance, got: %s", rr.Body.String())
	}
}

func TestBindKeyHandler_NebiusInvalidKeyBlacklist(t *testing.T) {
	st, cleanup := testutil.OpenTestStore(t)
	defer cleanup()
	provider := mockProviderServer(t, providerMockConfig{nebiusStatus: http.StatusUnauthorized})
	restore := appagent.SetVendorBaseURLsForTesting(provider.URL, provider.URL)
	t.Cleanup(restore)
	router := newTestRouter(st, testServerConfig())

	ctx := context.Background()
	if err := st.UpsertProviderRate(ctx, "nebius", 0.0001, 1000, 1); err != nil {
		t.Fatalf("upsert provider rate: %v", err)
	}

	apiKey := "apa_key_nb_bad"
	agentID, err := st.CreateAgent(ctx, "AgentNebiusBad", apiKey, "claim-"+apiKey)
	if err != nil {
		t.Fatalf("create agent: %v", err)
	}
	if err := st.EnsureAccount(ctx, agentID, 0); err != nil {
		t.Fatalf("ensure account: %v", err)
	}

	body := []byte(`{"provider":"nebius","api_key":"nb-bad","budget_usd":10}`)
	for i := 0; i < 3; i++ {
		req := httptest.NewRequest(http.MethodPost, "/api/agents/bind_key", bytes.NewReader(body))
		req.Header.Set("Authorization", "Bearer "+apiKey)
		rr := httptest.NewRecorder()
		router.ServeHTTP(rr, req)
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

func TestBindKeyHandler_BudgetLimit(t *testing.T) {
	st, cleanup := testutil.OpenTestStore(t)
	defer cleanup()
	provider := mockProviderServer(t, providerMockConfig{openRouterStatus: http.StatusOK, openRouterBody: `{"limit_remaining":100}`})
	restore := appagent.SetVendorBaseURLsForTesting(provider.URL, provider.URL)
	t.Cleanup(restore)
	router := newTestRouter(st, testServerConfig())

	ctx := context.Background()
	if err := st.UpsertProviderRate(ctx, "openrouter", 0.0001, 1000, 1); err != nil {
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

	body := []byte(`{"provider":"openrouter","api_key":"or-test","budget_usd":21}`)
	req := httptest.NewRequest(http.MethodPost, "/api/agents/bind_key", bytes.NewReader(body))
	req.Header.Set("Authorization", "Bearer "+apiKey)
	rr := httptest.NewRecorder()

	router.ServeHTTP(rr, req)
	if rr.Code != http.StatusBadRequest {
		t.Fatalf("expected 400, got %d: %s", rr.Code, rr.Body.String())
	}
}

func TestBindKeyHandler_Cooldown(t *testing.T) {
	st, cleanup := testutil.OpenTestStore(t)
	defer cleanup()
	provider := mockProviderServer(t, providerMockConfig{openRouterStatus: http.StatusOK, openRouterBody: `{"limit_remaining":100}`})
	restore := appagent.SetVendorBaseURLsForTesting(provider.URL, provider.URL)
	t.Cleanup(restore)
	router := newTestRouter(st, testServerConfig())

	ctx := context.Background()
	if err := st.UpsertProviderRate(ctx, "openrouter", 0.0001, 1000, 1); err != nil {
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

	body1 := []byte(`{"provider":"openrouter","api_key":"or-test-1","budget_usd":10}`)
	req1 := httptest.NewRequest(http.MethodPost, "/api/agents/bind_key", bytes.NewReader(body1))
	req1.Header.Set("Authorization", "Bearer "+apiKey)
	rr1 := httptest.NewRecorder()
	router.ServeHTTP(rr1, req1)
	if rr1.Code != http.StatusOK {
		t.Fatalf("expected first bind 200, got %d: %s", rr1.Code, rr1.Body.String())
	}

	body2 := []byte(`{"provider":"openrouter","api_key":"or-test-2","budget_usd":10}`)
	req2 := httptest.NewRequest(http.MethodPost, "/api/agents/bind_key", bytes.NewReader(body2))
	req2.Header.Set("Authorization", "Bearer "+apiKey)
	rr2 := httptest.NewRecorder()
	router.ServeHTTP(rr2, req2)
	if rr2.Code != http.StatusTooManyRequests {
		t.Fatalf("expected 429, got %d: %s", rr2.Code, rr2.Body.String())
	}
}

func TestAgentMeHandler(t *testing.T) {
	st, cleanup := testutil.OpenTestStore(t)
	defer cleanup()
	router := newTestRouter(st, config.ServerConfig{})

	ctx := context.Background()
	apiKey := "apa_key_me"
	agentID, err := st.CreateAgent(ctx, "AgentMe", apiKey, "claim-"+apiKey)
	if err != nil {
		t.Fatalf("create agent: %v", err)
	}

	req := httptest.NewRequest(http.MethodGet, "/api/agents/me", nil)
	req.Header.Set("Authorization", "Bearer "+apiKey)
	rr := httptest.NewRecorder()

	router.ServeHTTP(rr, req)
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
	router := newTestRouter(st, config.ServerConfig{})

	req := httptest.NewRequest(http.MethodGet, "/api/agents/me", nil)
	rr := httptest.NewRecorder()

	router.ServeHTTP(rr, req)
	if rr.Code != http.StatusUnauthorized {
		t.Fatalf("expected 401, got %d: %s", rr.Code, rr.Body.String())
	}
}

type providerMockConfig struct {
	openRouterStatus int
	openRouterBody   string
	nebiusStatus     int
	nebiusBody       string
}

func mockProviderServer(t *testing.T, cfg providerMockConfig) *httptest.Server {
	t.Helper()
	if cfg.openRouterStatus == 0 {
		cfg.openRouterStatus = http.StatusOK
	}
	if cfg.nebiusStatus == 0 {
		cfg.nebiusStatus = http.StatusOK
	}
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch r.URL.Path {
		case "/key":
			w.WriteHeader(cfg.openRouterStatus)
			if cfg.openRouterBody != "" {
				_, _ = w.Write([]byte(cfg.openRouterBody))
			}
		case "/credits":
			w.WriteHeader(cfg.nebiusStatus)
			if cfg.nebiusBody != "" {
				_, _ = w.Write([]byte(cfg.nebiusBody))
			}
		default:
			w.WriteHeader(http.StatusNotFound)
		}
	}))
	t.Cleanup(srv.Close)
	return srv
}

func testServerConfig() config.ServerConfig {
	return config.ServerConfig{
		MaxBudgetUSD:     20,
		BindCooldownMins: 60,
	}
}
