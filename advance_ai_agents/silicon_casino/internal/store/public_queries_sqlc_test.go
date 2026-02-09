package store

import "testing"

func TestPublicLeaderboardOrdering(t *testing.T) {
	st, ctx, cleanup := openStore(t)
	defer cleanup()

	a1 := mustCreateAgent(t, st, ctx, "A", "key-a", 1000)
	a2 := mustCreateAgent(t, st, ctx, "B", "key-b", 1000)

	_, err := st.Credit(ctx, a1, 500, "topup_credit", "topup", NewID())
	if err != nil {
		t.Fatalf("credit a1: %v", err)
	}
	_, err = st.Debit(ctx, a2, 200, "bet_debit", "hand", NewID())
	if err != nil {
		t.Fatalf("debit a2: %v", err)
	}

	lb, err := st.ListLeaderboard(ctx, 10, 0)
	if err != nil {
		t.Fatalf("list leaderboard: %v", err)
	}
	if len(lb) < 2 {
		t.Fatalf("expected 2+ leaderboard entries")
	}
	if lb[0].AgentID != a1 {
		t.Fatalf("expected %s first, got %s", a1, lb[0].AgentID)
	}
}
