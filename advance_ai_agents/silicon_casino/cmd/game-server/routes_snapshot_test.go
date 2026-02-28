package main

import (
	"net/http"
	"reflect"
	"sort"
	"testing"

	"silicon-casino/internal/config"
	"silicon-casino/internal/testutil"

	"github.com/go-chi/chi/v5"
)

func TestRouteSnapshot(t *testing.T) {
	st, cleanup := testutil.OpenTestStore(t)
	defer cleanup()
	router := newTestRouter(st, config.ServerConfig{AdminAPIKey: "admin-key"})

	var routes []string
	err := chi.Walk(router, func(method string, route string, _ http.Handler, _ ...func(http.Handler) http.Handler) error {
		routes = append(routes, method+" "+route)
		return nil
	})
	if err != nil {
		t.Fatalf("walk routes: %v", err)
	}
	sort.Strings(routes)

	expected := []string{
		"DELETE /api/agent/sessions/{session_id}",
		"GET /api/agent/sessions/{session_id}/events",
		"GET /api/agent/sessions/{session_id}/state",
		"GET /api/agents",
		"GET /api/agents/me",
		"GET /api/debug/vars",
		"GET /api/ledger",
		"GET /api/providers/rates",
		"GET /api/public/agent-table",
		"GET /api/public/agents/{agent_id}/profile",
		"GET /api/public/agents/{agent_id}/tables",
		"GET /api/public/leaderboard",
		"GET /api/public/rooms",
		"GET /api/public/spectate/events",
		"GET /api/public/spectate/state",
		"GET /api/public/tables",
		"GET /api/public/tables/history",
		"GET /api/public/tables/{table_id}/replay",
		"GET /api/public/tables/{table_id}/snapshot",
		"GET /api/public/tables/{table_id}/timeline",
		"GET /claim/{claim_code}",
		"GET /healthz",
		"GET /mcp",
		"OPTIONS /mcp",
		"DELETE /mcp",
		"POST /api/agent/sessions",
		"POST /api/agent/sessions/{session_id}/actions",
		"POST /api/agents/bind_key",
		"POST /api/agents/claim",
		"POST /api/agents/register",
		"POST /api/providers/rates",
		"POST /api/rooms",
		"POST /api/topup",
		"POST /mcp",
	}
	sort.Strings(expected)

	if !reflect.DeepEqual(routes, expected) {
		t.Fatalf("route snapshot mismatch\nexpected=%v\nactual=%v", expected, routes)
	}
}
