package main

import (
	"bytes"
	"net/http"
	"net/http/httptest"
	"testing"

	"silicon-casino/internal/agentgateway"
	"silicon-casino/internal/config"
	"silicon-casino/internal/ledger"
	"silicon-casino/internal/testutil"
)

func TestRoutesAndAgentEndpoints(t *testing.T) {
	st, cleanup := testutil.OpenTestStore(t)
	defer cleanup()
	if err := st.EnsureDefaultRooms(t.Context()); err != nil {
		t.Fatalf("ensure rooms: %v", err)
	}
	coord := agentgateway.NewCoordinator(st, ledger.New(st))
	router := newRouter(st, config.ServerConfig{AdminAPIKey: "admin-key"}, coord)

	req := httptest.NewRequest(http.MethodGet, "/healthz", nil)
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)
	if w.Code != http.StatusOK {
		t.Fatalf("expected /healthz 200, got %d", w.Code)
	}

	req = httptest.NewRequest(http.MethodPost, "/api/agent/sessions", nil)
	w = httptest.NewRecorder()
	router.ServeHTTP(w, req)
	// Empty body should fail decode and prove route is mounted.
	if w.Code != http.StatusBadRequest {
		t.Fatalf("expected /api/agent/sessions 400, got %d", w.Code)
	}

	req = httptest.NewRequest(http.MethodOptions, "/mcp", nil)
	w = httptest.NewRecorder()
	router.ServeHTTP(w, req)
	if w.Code != http.StatusNoContent {
		t.Fatalf("expected /mcp OPTIONS 204, got %d", w.Code)
	}

	initBody := []byte(`{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"test-client","version":"1.0.0"}}}`)
	req = httptest.NewRequest(http.MethodPost, "/mcp", bytes.NewReader(initBody))
	req.Header.Set("Content-Type", "application/json")
	w = httptest.NewRecorder()
	router.ServeHTTP(w, req)
	if w.Code != http.StatusOK {
		t.Fatalf("expected /mcp POST initialize 200, got %d body=%s", w.Code, w.Body.String())
	}
}
