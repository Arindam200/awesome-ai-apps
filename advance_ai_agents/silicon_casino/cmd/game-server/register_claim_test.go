package main

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"silicon-casino/internal/config"
	"silicon-casino/internal/testutil"
)

func TestRegisterAgentHandler(t *testing.T) {
	st, cleanup := testutil.OpenTestStore(t)
	defer cleanup()
	router := newTestRouter(st, config.ServerConfig{})

	body := `{"name":"AgentA","description":"test"}`
	req := httptest.NewRequest(http.MethodPost, "/api/agents/register", bytes.NewBufferString(body))
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)
	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}

	var resp struct {
		Agent struct {
			AgentID string `json:"agent_id"`
			APIKey  string `json:"api_key"`
			Code    string `json:"verification_code"`
		} `json:"agent"`
	}
	if err := json.NewDecoder(w.Body).Decode(&resp); err != nil {
		t.Fatalf("decode response: %v", err)
	}
	if resp.Agent.AgentID == "" || resp.Agent.APIKey == "" || resp.Agent.Code == "" {
		t.Fatalf("expected agent_id/api_key/verification_code in response")
	}
}

func TestRegisterAgentHandlerInvalidBody(t *testing.T) {
	st, cleanup := testutil.OpenTestStore(t)
	defer cleanup()
	router := newTestRouter(st, config.ServerConfig{})

	req := httptest.NewRequest(http.MethodPost, "/api/agents/register", bytes.NewBufferString("{"))
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)
	if w.Code != http.StatusBadRequest {
		t.Fatalf("expected 400, got %d", w.Code)
	}

	req = httptest.NewRequest(http.MethodPost, "/api/agents/register", bytes.NewBufferString(`{"description":"missing name"}`))
	w = httptest.NewRecorder()
	router.ServeHTTP(w, req)
	if w.Code != http.StatusBadRequest {
		t.Fatalf("expected 400 for missing name, got %d", w.Code)
	}
}

func TestClaimAgentHandler(t *testing.T) {
	st, cleanup := testutil.OpenTestStore(t)
	defer cleanup()
	router := newTestRouter(st, config.ServerConfig{})

	body := `{"name":"AgentB","description":"test"}`
	req := httptest.NewRequest(http.MethodPost, "/api/agents/register", bytes.NewBufferString(body))
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)
	if w.Code != http.StatusOK {
		t.Fatalf("register expected 200, got %d", w.Code)
	}
	var reg struct {
		Agent struct {
			AgentID string `json:"agent_id"`
			Code    string `json:"verification_code"`
		} `json:"agent"`
	}
	if err := json.NewDecoder(w.Body).Decode(&reg); err != nil {
		t.Fatalf("decode register: %v", err)
	}

	claimBody := map[string]string{
		"agent_id":  reg.Agent.AgentID,
		"claim_code": reg.Agent.Code,
	}
	claimBytes, _ := json.Marshal(claimBody)
	req = httptest.NewRequest(http.MethodPost, "/api/agents/claim", bytes.NewReader(claimBytes))
	w = httptest.NewRecorder()
	router.ServeHTTP(w, req)
	if w.Code != http.StatusOK {
		t.Fatalf("claim expected 200, got %d: %s", w.Code, w.Body.String())
	}

	// Invalid claim code should be unauthorized.
	claimBody["claim_code"] = "apa_claim_invalid"
	claimBytes, _ = json.Marshal(claimBody)
	req = httptest.NewRequest(http.MethodPost, "/api/agents/claim", bytes.NewReader(claimBytes))
	w = httptest.NewRecorder()
	router.ServeHTTP(w, req)
	if w.Code != http.StatusUnauthorized {
		t.Fatalf("expected 401 for invalid claim code, got %d", w.Code)
	}
}

func TestClaimByCodeHandler(t *testing.T) {
	st, cleanup := testutil.OpenTestStore(t)
	defer cleanup()
	router := newTestRouter(st, config.ServerConfig{})

	body := `{"name":"AgentC","description":"test"}`
	req := httptest.NewRequest(http.MethodPost, "/api/agents/register", bytes.NewBufferString(body))
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)
	if w.Code != http.StatusOK {
		t.Fatalf("register expected 200, got %d", w.Code)
	}
	var reg struct {
		Agent struct {
			AgentID string `json:"agent_id"`
			Code    string `json:"verification_code"`
		} `json:"agent"`
	}
	if err := json.NewDecoder(w.Body).Decode(&reg); err != nil {
		t.Fatalf("decode register: %v", err)
	}

	req = httptest.NewRequest(http.MethodGet, "/claim/"+reg.Agent.Code, nil)
	w = httptest.NewRecorder()
	router.ServeHTTP(w, req)
	if w.Code != http.StatusOK {
		t.Fatalf("claim by code expected 200, got %d: %s", w.Code, w.Body.String())
	}

	req = httptest.NewRequest(http.MethodGet, "/claim/apa_claim_missing", nil)
	w = httptest.NewRecorder()
	router.ServeHTTP(w, req)
	if w.Code != http.StatusNotFound {
		t.Fatalf("claim by code expected 404, got %d", w.Code)
	}
}
