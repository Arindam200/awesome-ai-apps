package main

import (
	"strconv"
	"testing"
	"time"

	"silicon-casino/internal/agentgateway"
	"silicon-casino/internal/config"
	"silicon-casino/internal/ledger"
	"silicon-casino/internal/store"

	"github.com/go-chi/chi/v5"
)

func newTestRouter(st *store.Store, cfg config.ServerConfig) *chi.Mux {
	coord := agentgateway.NewCoordinator(st, ledger.New(st))
	return newRouter(st, cfg, coord)
}

func createTestAgent(t *testing.T, st *store.Store, name string) (string, string, string) {
	t.Helper()
	suffix := strconv.FormatInt(time.Now().UnixNano(), 10)
	apiKey := "apa_test_" + suffix
	claimCode := "apa_claim_test_" + suffix
	id, err := st.CreateAgent(t.Context(), name, apiKey, claimCode)
	if err != nil {
		t.Fatalf("create agent: %v", err)
	}
	if err := st.EnsureAccount(t.Context(), id, 1000); err != nil {
		t.Fatalf("ensure account: %v", err)
	}
	return id, apiKey, claimCode
}
