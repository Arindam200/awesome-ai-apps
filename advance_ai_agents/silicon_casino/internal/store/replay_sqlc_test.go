package store

import (
	"context"
	"encoding/json"
	"testing"
)

func TestTableReplayRoundtrip(t *testing.T) {
	st, ctx, cleanup := openStore(t)
	defer cleanup()

	agentID := mustCreateAgent(t, st, ctx, "bot-a", "key-a", 10000)
	roomID, err := st.CreateRoom(ctx, "Replay", 1000, 50, 100)
	if err != nil {
		t.Fatalf("create room: %v", err)
	}
	tableID, err := st.CreateTable(ctx, roomID, "active", 50, 100)
	if err != nil {
		t.Fatalf("create table: %v", err)
	}
	handID, err := st.CreateHand(ctx, tableID)
	if err != nil {
		t.Fatalf("create hand: %v", err)
	}

	payload := json.RawMessage(`{"pot_cc":150,"street":"preflop"}`)
	var handSeq int32 = 0
	if err := st.InsertTableReplayEvent(ctx, tableID, handID, 1, &handSeq, "hand_started", agentID, payload, 1); err != nil {
		t.Fatalf("insert replay event: %v", err)
	}
	if err := st.InsertTableReplaySnapshot(ctx, tableID, 1, json.RawMessage(`{"pot_cc":150}`), 1); err != nil {
		t.Fatalf("insert replay snapshot: %v", err)
	}

	events, err := st.ListTableReplayEventsFromSeq(ctx, tableID, 1, 10)
	if err != nil {
		t.Fatalf("list replay events: %v", err)
	}
	if len(events) != 1 {
		t.Fatalf("expected 1 event, got %d", len(events))
	}
	if events[0].EventType != "hand_started" {
		t.Fatalf("unexpected event type: %s", events[0].EventType)
	}

	snap, err := st.GetLatestTableReplaySnapshotAtOrBefore(ctx, tableID, 1)
	if err != nil {
		t.Fatalf("get latest snapshot: %v", err)
	}
	if snap.AtGlobalSeq != 1 {
		t.Fatalf("expected snapshot seq=1, got %d", snap.AtGlobalSeq)
	}

	lastSeq, err := st.GetTableReplayLastSeq(ctx, tableID)
	if err != nil {
		t.Fatalf("get replay last seq: %v", err)
	}
	if lastSeq != 1 {
		t.Fatalf("expected last seq=1, got %d", lastSeq)
	}

	pot := int64(150)
	if err := st.EndHandWithSummary(context.Background(), handID, agentID, &pot, "preflop"); err != nil {
		t.Fatalf("end hand with summary: %v", err)
	}
	h, err := st.GetHandByID(ctx, handID)
	if err != nil {
		t.Fatalf("get hand by id: %v", err)
	}
	if h.WinnerAgentID != agentID {
		t.Fatalf("winner mismatch: %s", h.WinnerAgentID)
	}
	if h.PotCC == nil || *h.PotCC != pot {
		t.Fatalf("pot mismatch: %+v", h.PotCC)
	}
}
