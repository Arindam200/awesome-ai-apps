package spectatorgateway

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"silicon-casino/internal/agentgateway"
	"silicon-casino/internal/ledger"
	"silicon-casino/internal/testutil"
)

func setupCoordWithTable(t *testing.T) (*agentgateway.Coordinator, string) {
	t.Helper()
	st, cleanup := testutil.OpenTestStore(t)
	t.Cleanup(cleanup)
	ctx := context.Background()
	if err := st.EnsureDefaultRooms(ctx); err != nil {
		t.Fatalf("ensure rooms: %v", err)
	}
	a1, _ := st.CreateAgent(ctx, "a1", "k1", "claim-k1")
	a2, _ := st.CreateAgent(ctx, "a2", "k2", "claim-k2")
	_ = st.EnsureAccount(ctx, a1, 100000)
	_ = st.EnsureAccount(ctx, a2, 100000)
	coord := agentgateway.NewCoordinator(st, ledger.New(st))
	if _, err := coord.CreateSession(ctx, agentgateway.CreateSessionRequest{AgentID: a1, APIKey: "k1", JoinMode: "random"}); err != nil {
		t.Fatalf("create session1: %v", err)
	}
	s2, err := coord.CreateSession(ctx, agentgateway.CreateSessionRequest{AgentID: a2, APIKey: "k2", JoinMode: "random"})
	if err != nil {
		t.Fatalf("create session2: %v", err)
	}
	if s2.TableID == "" {
		t.Fatal("expected table_id")
	}
	return coord, s2.TableID
}

func TestSpectatorStateIncludesHoleCards(t *testing.T) {
	coord, tableID := setupCoordWithTable(t)
	req := httptest.NewRequest(http.MethodGet, "/api/public/spectate/state?table_id="+tableID, nil)
	w := httptest.NewRecorder()
	StateHandler(coord).ServeHTTP(w, req)
	if w.Code != http.StatusOK {
		t.Fatalf("expected 200 got %d body=%s", w.Code, w.Body.String())
	}
	var body map[string]any
	if err := json.Unmarshal(w.Body.Bytes(), &body); err != nil {
		t.Fatalf("decode body: %v", err)
	}
	if _, ok := body["my_hole_cards"]; ok {
		t.Fatalf("public state should not contain my_hole_cards: %v", body)
	}
	seats := body["seats"].([]any)
	for _, seat := range seats {
		hole, ok := seat.(map[string]any)["hole_cards"]
		if !ok {
			t.Fatalf("public seat missing hole cards: %v", seat)
		}
		cards, ok := hole.([]any)
		if !ok || len(cards) != 2 {
			t.Fatalf("public seat hole cards invalid: %v", seat)
		}
	}
}
