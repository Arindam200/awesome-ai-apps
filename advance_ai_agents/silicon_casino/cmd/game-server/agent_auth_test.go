package main

import (
	"bytes"
	"net/http"
	"net/http/httptest"
	"testing"

	"silicon-casino/internal/config"
	"silicon-casino/internal/testutil"
)

func TestAgentAuthMiddleware(t *testing.T) {
	st, cleanup := testutil.OpenTestStore(t)
	defer cleanup()
	cfg := config.ServerConfig{
		AllowAnyVendorKey: true,
		MaxBudgetUSD:      20,
	}
	router := newTestRouter(st, cfg)

	agentID, apiKey, _ := createTestAgent(t, st, "AuthAgent")
	if agentID == "" || apiKey == "" {
		t.Fatal("expected agent credentials")
	}

	req := httptest.NewRequest(http.MethodGet, "/api/agents/me", nil)
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)
	if w.Code != http.StatusUnauthorized {
		t.Fatalf("missing token expected 401, got %d", w.Code)
	}

	req = httptest.NewRequest(http.MethodGet, "/api/agents/me", nil)
	req.Header.Set("Authorization", "Bearer apa_invalid")
	w = httptest.NewRecorder()
	router.ServeHTTP(w, req)
	if w.Code != http.StatusUnauthorized {
		t.Fatalf("wrong token expected 401, got %d", w.Code)
	}

	req = httptest.NewRequest(http.MethodGet, "/api/agents/me", nil)
	req.Header.Set("Authorization", "Bearer "+apiKey)
	w = httptest.NewRecorder()
	router.ServeHTTP(w, req)
	if w.Code != http.StatusOK {
		t.Fatalf("valid token expected 200, got %d: %s", w.Code, w.Body.String())
	}

	// bind_key should pass auth but reject invalid body.
	req = httptest.NewRequest(http.MethodPost, "/api/agents/bind_key", bytes.NewBufferString(`{}`))
	req.Header.Set("Authorization", "Bearer "+apiKey)
	w = httptest.NewRecorder()
	router.ServeHTTP(w, req)
	if w.Code != http.StatusBadRequest {
		t.Fatalf("bind_key invalid body expected 400, got %d", w.Code)
	}
}
