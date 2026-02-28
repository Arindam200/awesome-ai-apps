package store

import "testing"

func TestAccountsEnsureGetList(t *testing.T) {
	st, ctx, cleanup := openStore(t)
	defer cleanup()

	agentID := mustCreateAgent(t, st, ctx, "A", "key-a", 1234)

	bal, err := st.GetAccountBalance(ctx, agentID)
	if err != nil {
		t.Fatalf("get account balance: %v", err)
	}
	if bal != 1234 {
		t.Fatalf("expected 1234, got %d", bal)
	}

	items, err := st.ListAccounts(ctx, agentID, 10, 0)
	if err != nil {
		t.Fatalf("list accounts: %v", err)
	}
	if len(items) != 1 || items[0].AgentID != agentID {
		t.Fatalf("unexpected account list: %+v", items)
	}
}
