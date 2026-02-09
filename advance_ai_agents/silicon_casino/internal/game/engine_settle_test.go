package game

import (
	"context"
	"testing"

	"silicon-casino/internal/ledger"
	"silicon-casino/internal/testutil"
)

func TestSettleTransfersCCOnly(t *testing.T) {
	st, cleanup := testutil.OpenTestStore(t)
	defer cleanup()

	ctx := context.Background()
	agent0, err := st.CreateAgent(ctx, "A", "key-a", "claim-key-a")
	if err != nil {
		t.Fatalf("create agent A: %v", err)
	}
	agent1, err := st.CreateAgent(ctx, "B", "key-b", "claim-key-b")
	if err != nil {
		t.Fatalf("create agent B: %v", err)
	}
	if err := st.EnsureAccount(ctx, agent0, 10000); err != nil {
		t.Fatalf("ensure account A: %v", err)
	}
	if err := st.EnsureAccount(ctx, agent1, 10000); err != nil {
		t.Fatalf("ensure account B: %v", err)
	}

	roomID := "room-test"
	tableID, err := st.CreateTable(ctx, roomID, "active", 50, 100)
	if err != nil {
		t.Fatalf("create table: %v", err)
	}

	eng := NewEngine(st, ledger.New(st), tableID, 50, 100)
	p0 := &Player{ID: agent0, Name: "A", Seat: 0}
	p1 := &Player{ID: agent1, Name: "B", Seat: 1}
	if err := eng.StartHand(ctx, p0, p1, 50, 100); err != nil {
		t.Fatalf("start hand: %v", err)
	}

	sbIdx := eng.State.DealerPos
	if _, err := eng.ApplyAction(ctx, Action{Player: sbIdx, Type: ActionFold}); err != nil {
		t.Fatalf("apply fold: %v", err)
	}
	_, err = eng.Settle(ctx)
	if err != nil {
		t.Fatalf("settle: %v", err)
	}

	bal0, _ := st.GetAccountBalance(ctx, agent0)
	bal1, _ := st.GetAccountBalance(ctx, agent1)

	// Dealer posts small blind, so BB should win the 150 pot after SB folds.
	if sbIdx == 1 {
		if bal0 != 10050 || bal1 != 9950 {
			t.Fatalf("expected A=10050 B=9950, got A=%d B=%d", bal0, bal1)
		}
	} else {
		if bal1 != 10050 || bal0 != 9950 {
			t.Fatalf("expected A=9950 B=10050, got A=%d B=%d", bal0, bal1)
		}
	}
}
