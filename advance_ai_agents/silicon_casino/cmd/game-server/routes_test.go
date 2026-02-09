package main

import (
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
}
