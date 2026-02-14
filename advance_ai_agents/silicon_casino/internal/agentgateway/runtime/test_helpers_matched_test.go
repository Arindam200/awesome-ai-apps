package runtime

import (
	"context"
	"testing"

	"silicon-casino/internal/ledger"
	"silicon-casino/internal/testutil"
)

func setupMatchedSessions(t *testing.T) (*Coordinator, string, string) {
	t.Helper()
	st, cleanup := testutil.OpenTestStore(t)
	t.Cleanup(cleanup)
	ctx := context.Background()
	if err := st.EnsureDefaultRooms(ctx); err != nil {
		t.Fatalf("ensure rooms: %v", err)
	}
	a1, err := st.CreateAgent(ctx, "bot-a", "key-a", "claim-key-a")
	if err != nil {
		t.Fatalf("create a1: %v", err)
	}
	a2, err := st.CreateAgent(ctx, "bot-b", "key-b", "claim-key-b")
	if err != nil {
		t.Fatalf("create a2: %v", err)
	}
	if err := st.EnsureAccount(ctx, a1, 100000); err != nil {
		t.Fatalf("ensure account a1: %v", err)
	}
	if err := st.EnsureAccount(ctx, a2, 100000); err != nil {
		t.Fatalf("ensure account a2: %v", err)
	}
	coord := NewCoordinator(st, ledger.New(st))
	if _, err := coord.CreateSession(ctx, CreateSessionRequest{AgentID: a1, APIKey: "key-a", JoinMode: "random"}); err != nil {
		t.Fatalf("create session 1: %v", err)
	}
	s2, err := coord.CreateSession(ctx, CreateSessionRequest{AgentID: a2, APIKey: "key-b", JoinMode: "random"})
	if err != nil {
		t.Fatalf("create session 2: %v", err)
	}
	var s1ID string
	coord.mu.Lock()
	for id, sess := range coord.sessions {
		if sess.agent.ID == a1 {
			s1ID = id
		}
	}
	coord.mu.Unlock()
	return coord, s1ID, s2.SessionID
}
