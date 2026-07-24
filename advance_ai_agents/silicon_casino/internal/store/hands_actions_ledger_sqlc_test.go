package store

import "testing"

func TestHandsActionsAndLedgerQuery(t *testing.T) {
	st, ctx, cleanup := openStore(t)
	defer cleanup()

	roomID, _ := st.CreateRoom(ctx, "Low", 1000, 50, 100)
	tableID, err := st.CreateTable(ctx, roomID, "active", 50, 100)
	if err != nil {
		t.Fatalf("create table: %v", err)
	}
	agentID := mustCreateAgent(t, st, ctx, "A", "key-a", 10000)

	handID, err := st.CreateHand(ctx, tableID)
	if err != nil {
		t.Fatalf("create hand: %v", err)
	}
	if err := st.RecordAction(ctx, handID, agentID, "bet", 200); err != nil {
		t.Fatalf("record action: %v", err)
	}
	if _, err := st.Debit(ctx, agentID, 200, "bet_debit", "hand", handID); err != nil {
		t.Fatalf("debit: %v", err)
	}
	if err := st.EndHand(ctx, handID); err != nil {
		t.Fatalf("end hand: %v", err)
	}

	entries, err := st.ListLedgerEntries(ctx, LedgerFilter{AgentID: agentID, HandID: handID}, 10, 0)
	if err != nil {
		t.Fatalf("list ledger entries: %v", err)
	}
	if len(entries) == 0 {
		t.Fatalf("expected ledger entries")
	}
}
