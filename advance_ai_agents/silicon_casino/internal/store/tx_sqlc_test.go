package store

import "testing"

func TestTxDebitCreditConsistency(t *testing.T) {
	st, ctx, cleanup := openStore(t)
	defer cleanup()

	agentID := mustCreateAgent(t, st, ctx, "A", "key-a", 1000)

	if _, err := st.Debit(ctx, agentID, 2000, "bet_debit", "hand", NewID()); err == nil {
		t.Fatalf("expected insufficient balance")
	}

	bal, err := st.Credit(ctx, agentID, 300, "topup_credit", "topup", NewID())
	if err != nil {
		t.Fatalf("credit failed: %v", err)
	}
	if bal != 1300 {
		t.Fatalf("expected 1300, got %d", bal)
	}
	bal, err = st.Debit(ctx, agentID, 500, "bet_debit", "hand", NewID())
	if err != nil {
		t.Fatalf("debit failed: %v", err)
	}
	if bal != 800 {
		t.Fatalf("expected 800, got %d", bal)
	}

	entries, err := st.ListLedgerEntries(ctx, LedgerFilter{AgentID: agentID}, 10, 0)
	if err != nil {
		t.Fatalf("list ledger entries: %v", err)
	}
	if len(entries) < 2 {
		t.Fatalf("expected at least 2 ledger entries, got %d", len(entries))
	}
}
