package mcpserver

import (
	"context"
	"encoding/json"
	"net/http/httptest"
	"sort"
	"testing"

	"silicon-casino/internal/agentgateway"
	"silicon-casino/internal/config"
	"silicon-casino/internal/ledger"
	"silicon-casino/internal/store"
	"silicon-casino/internal/testutil"

	"github.com/mark3labs/mcp-go/client"
	"github.com/mark3labs/mcp-go/client/transport"
	"github.com/mark3labs/mcp-go/mcp"
)

func TestMCPServerToolsAndFlows(t *testing.T) {
	st, cleanup := testutil.OpenTestStore(t)
	defer cleanup()
	ctx := context.Background()
	if err := st.EnsureDefaultRooms(ctx); err != nil {
		t.Fatalf("ensure rooms: %v", err)
	}
	if err := st.EnsureDefaultProviderRates(ctx, defaultRates()); err != nil {
		t.Fatalf("ensure rates: %v", err)
	}

	cfg := config.ServerConfig{AllowAnyVendorKey: true, MaxBudgetUSD: 20, BindCooldownMins: 60}
	srv := New(st, cfg, newCoordinator(st))
	httpSrv := httptest.NewServer(srv.Handler())
	defer httpSrv.Close()

	mcpClient, closeClient := newMCPClient(t, httpSrv.URL+"/mcp")
	defer closeClient()

	tools := mustListTools(t, mcpClient)
	assertToolNames(t, tools,
		"register_agent",
		"claim_agent",
		"bind_vendor_key",
		"next_decision",
		"submit_next_decision",
		"list_rooms",
		"list_live_tables",
		"get_leaderboard",
		"find_agent_table",
	)

	a1 := mustRegisterAndClaim(t, mcpClient, "mcp-bot-a")
	a2 := mustRegisterAndClaim(t, mcpClient, "mcp-bot-b")

	bindRes := mustCallTool(t, mcpClient, "bind_vendor_key", map[string]any{
		"agent_id":   a1.AgentID,
		"api_key":    a1.APIKey,
		"provider":   "openai",
		"vendor_key": "vendor-key-a",
		"budget_usd": 1,
	})
	if bindRes.IsError {
		t.Fatalf("bind_vendor_key expected success, got: %v", bindRes.StructuredContent)
	}

	for _, toolName := range []string{"list_rooms", "list_live_tables", "get_leaderboard"} {
		res := mustCallTool(t, mcpClient, toolName, map[string]any{})
		if res.IsError {
			t.Fatalf("%s expected success, got: %v", toolName, res.StructuredContent)
		}
	}

	n1 := mustCallTool(t, mcpClient, "next_decision", map[string]any{"agent_id": a1.AgentID, "api_key": a1.APIKey, "mode": "random"})
	n2 := mustCallTool(t, mcpClient, "next_decision", map[string]any{"agent_id": a2.AgentID, "api_key": a2.APIKey, "mode": "random"})
	if n1.IsError || n2.IsError {
		t.Fatalf("next_decision should succeed, n1=%v n2=%v", n1.StructuredContent, n2.StructuredContent)
	}

	picked := pickDecisionRequest(t, []decisionCandidate{{AgentID: a1.AgentID, APIKey: a1.APIKey, Result: n1}, {AgentID: a2.AgentID, APIKey: a2.APIKey, Result: n2}})
	if picked == nil {
		r1 := mustCallTool(t, mcpClient, "next_decision", map[string]any{"agent_id": a1.AgentID, "api_key": a1.APIKey, "mode": "random"})
		r2 := mustCallTool(t, mcpClient, "next_decision", map[string]any{"agent_id": a2.AgentID, "api_key": a2.APIKey, "mode": "random"})
		picked = pickDecisionRequest(t, []decisionCandidate{{AgentID: a1.AgentID, APIKey: a1.APIKey, Result: r1}, {AgentID: a2.AgentID, APIKey: a2.APIKey, Result: r2}})
	}
	if picked == nil {
		t.Fatalf("expected decision_request from at least one agent")
	}

	submitArgs := map[string]any{
		"agent_id":    picked.AgentID,
		"api_key":     picked.APIKey,
		"decision_id": picked.DecisionID,
		"action":      picked.Action,
	}
	if picked.Amount != nil {
		submitArgs["amount"] = *picked.Amount
	}
	submitRes := mustCallTool(t, mcpClient, "submit_next_decision", submitArgs)
	if submitRes.IsError {
		t.Fatalf("submit_next_decision expected success, got: %v", submitRes.StructuredContent)
	}
}

func TestNextDecisionWaitingMatchmakingStatus(t *testing.T) {
	st, cleanup := testutil.OpenTestStore(t)
	defer cleanup()
	ctx := context.Background()
	if err := st.EnsureDefaultRooms(ctx); err != nil {
		t.Fatalf("ensure rooms: %v", err)
	}
	srv := New(st, config.ServerConfig{AllowAnyVendorKey: true}, newCoordinator(st))
	httpSrv := httptest.NewServer(srv.Handler())
	defer httpSrv.Close()

	mcpClient, closeClient := newMCPClient(t, httpSrv.URL+"/mcp")
	defer closeClient()

	a := mustRegisterAndClaim(t, mcpClient, "mcp-waiting")
	res := mustCallTool(t, mcpClient, "next_decision", map[string]any{
		"agent_id": a.AgentID,
		"api_key":  a.APIKey,
		"mode":     "random",
	})
	if res.IsError {
		t.Fatalf("next_decision expected noop, got error: %v", res.StructuredContent)
	}
	payload := mapFromStructured(t, res)
	if asString(payload["type"]) != "noop" {
		t.Fatalf("expected noop, got %v", payload)
	}
	if asString(payload["status"]) != "waiting_matchmaking" {
		t.Fatalf("expected waiting_matchmaking, got %v", payload)
	}
}

func TestMCPServerToolErrors(t *testing.T) {
	st, cleanup := testutil.OpenTestStore(t)
	defer cleanup()
	ctx := context.Background()
	if err := st.EnsureDefaultRooms(ctx); err != nil {
		t.Fatalf("ensure rooms: %v", err)
	}

	srv := New(st, config.ServerConfig{AllowAnyVendorKey: true}, newCoordinator(st))
	httpSrv := httptest.NewServer(srv.Handler())
	defer httpSrv.Close()

	mcpClient, closeClient := newMCPClient(t, httpSrv.URL+"/mcp")
	defer closeClient()

	missing := mustCallTool(t, mcpClient, "next_decision", map[string]any{"agent_id": "agent_x"})
	assertToolErrorCode(t, missing, "invalid_request")

	a := mustRegisterAndClaim(t, mcpClient, "mcp-bot-error")
	invalidDecision := mustCallTool(t, mcpClient, "submit_next_decision", map[string]any{
		"agent_id":    a.AgentID,
		"api_key":     a.APIKey,
		"decision_id": "dec_missing",
		"action":      "fold",
	})
	assertToolErrorCode(t, invalidDecision, "pending_decision_not_found")
}

type agentCreds struct {
	AgentID string
	APIKey  string
}

type decisionCandidate struct {
	AgentID string
	APIKey  string
	Result  *mcp.CallToolResult
}

type pickedDecision struct {
	AgentID    string
	APIKey     string
	DecisionID string
	Action     string
	Amount     *int64
}

func newCoordinator(st *store.Store) *agentgateway.Coordinator {
	return agentgateway.NewCoordinator(st, ledger.New(st))
}

func defaultRates() []store.ProviderRate {
	return []store.ProviderRate{
		{Provider: "openai", PricePer1KTokensUSD: 0.0001, CCPerUSD: 1000, Weight: 1},
		{Provider: "kimi", PricePer1KTokensUSD: 0.0001, CCPerUSD: 1000, Weight: 1},
	}
}

func newMCPClient(t *testing.T, endpoint string) (*client.Client, func()) {
	t.Helper()
	ctx := context.Background()
	trans, err := transport.NewStreamableHTTP(endpoint)
	if err != nil {
		t.Fatalf("new transport: %v", err)
	}
	if err := trans.Start(ctx); err != nil {
		t.Fatalf("transport start: %v", err)
	}
	c := client.NewClient(trans)
	_, err = c.Initialize(ctx, mcp.InitializeRequest{Params: mcp.InitializeParams{ProtocolVersion: mcp.LATEST_PROTOCOL_VERSION}})
	if err != nil {
		t.Fatalf("initialize: %v", err)
	}
	return c, func() { _ = trans.Close() }
}

func mustListTools(t *testing.T, c *client.Client) []mcp.Tool {
	t.Helper()
	res, err := c.ListTools(context.Background(), mcp.ListToolsRequest{})
	if err != nil {
		t.Fatalf("list tools: %v", err)
	}
	return res.Tools
}

func assertToolNames(t *testing.T, tools []mcp.Tool, expected ...string) {
	t.Helper()
	got := make([]string, 0, len(tools))
	for _, tool := range tools {
		got = append(got, tool.Name)
	}
	sort.Strings(got)
	sort.Strings(expected)
	if len(got) != len(expected) {
		t.Fatalf("tool count mismatch got=%v expected=%v", got, expected)
	}
	for i := range got {
		if got[i] != expected[i] {
			t.Fatalf("tool list mismatch got=%v expected=%v", got, expected)
		}
	}
}

func mustCallTool(t *testing.T, c *client.Client, name string, args map[string]any) *mcp.CallToolResult {
	t.Helper()
	res, err := c.CallTool(context.Background(), mcp.CallToolRequest{Params: mcp.CallToolParams{Name: name, Arguments: args}})
	if err != nil {
		t.Fatalf("call tool %s: %v", name, err)
	}
	return res
}

func mustRegisterAndClaim(t *testing.T, c *client.Client, name string) agentCreds {
	t.Helper()
	register := mustCallTool(t, c, "register_agent", map[string]any{"name": name})
	if register.IsError {
		t.Fatalf("register_agent error: %v", register.StructuredContent)
	}
	payload := mapFromStructured(t, register)
	agent, ok := payload["agent"].(map[string]any)
	if !ok {
		t.Fatalf("register_agent payload missing agent: %v", payload)
	}
	id := asString(agent["agent_id"])
	apiKey := asString(agent["api_key"])
	claimCode := asString(agent["verification_code"])
	if id == "" || apiKey == "" || claimCode == "" {
		t.Fatalf("register response missing fields: %v", agent)
	}

	claim := mustCallTool(t, c, "claim_agent", map[string]any{"agent_id": id, "claim_code": claimCode})
	if claim.IsError {
		t.Fatalf("claim_agent error: %v", claim.StructuredContent)
	}
	return agentCreds{AgentID: id, APIKey: apiKey}
}

func pickDecisionRequest(t *testing.T, cands []decisionCandidate) *pickedDecision {
	t.Helper()
	for _, c := range cands {
		payload := mapFromStructured(t, c.Result)
		if asString(payload["type"]) != "decision_request" {
			continue
		}
		decisionID := asString(payload["decision_id"])
		if decisionID == "" {
			t.Fatalf("decision_request missing decision_id: %v", payload)
		}
		state, _ := payload["state"].(map[string]any)
		action, amount := pickActionAndAmount(state)
		return &pickedDecision{AgentID: c.AgentID, APIKey: c.APIKey, DecisionID: decisionID, Action: action, Amount: amount}
	}
	return nil
}

func pickActionAndAmount(state map[string]any) (string, *int64) {
	legalRaw, _ := state["legal_actions"].([]any)
	legal := make([]string, 0, len(legalRaw))
	for _, a := range legalRaw {
		legal = append(legal, asString(a))
	}
	action := pickAction(legal)
	if action != "bet" && action != "raise" {
		return action, nil
	}
	constraints, _ := state["action_constraints"].(map[string]any)
	if action == "bet" {
		bet, _ := constraints["bet"].(map[string]any)
		min := int64(asFloat64(bet["min"]))
		return action, &min
	}
	raise, _ := constraints["raise"].(map[string]any)
	minTo := int64(asFloat64(raise["min_to"]))
	return action, &minTo
}

func pickAction(legal []string) string {
	priority := []string{"check", "call", "fold", "bet", "raise"}
	for _, p := range priority {
		for _, a := range legal {
			if a == p {
				return p
			}
		}
	}
	if len(legal) > 0 {
		return legal[0]
	}
	return "fold"
}

func assertToolErrorCode(t *testing.T, res *mcp.CallToolResult, want string) {
	t.Helper()
	if !res.IsError {
		t.Fatalf("expected tool error %q, got success: %v", want, res.StructuredContent)
	}
	payload := mapFromStructured(t, res)
	errObj, ok := payload["error"].(map[string]any)
	if !ok {
		t.Fatalf("error payload missing 'error': %v", payload)
	}
	got := asString(errObj["code"])
	if got != want {
		t.Fatalf("error code=%q want=%q payload=%v", got, want, payload)
	}
}

func mapFromStructured(t *testing.T, res *mcp.CallToolResult) map[string]any {
	t.Helper()
	b, err := json.Marshal(res.StructuredContent)
	if err != nil {
		t.Fatalf("marshal structured content: %v", err)
	}
	var out map[string]any
	if err := json.Unmarshal(b, &out); err != nil {
		t.Fatalf("unmarshal structured content: %v", err)
	}
	return out
}

func asString(v any) string {
	s, _ := v.(string)
	return s
}

func asFloat64(v any) float64 {
	f, _ := v.(float64)
	return f
}
