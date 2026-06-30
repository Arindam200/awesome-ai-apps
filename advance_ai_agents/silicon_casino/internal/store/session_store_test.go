package store

import (
	"testing"
	"time"
)

func TestAgentSessionStoreCRUD(t *testing.T) {
	st, ctx, cleanup := openStore(t)
	defer cleanup()

	agentID := mustCreateAgent(t, st, ctx, "BotA", "key-a", 10000)
	roomID, err := st.CreateRoom(ctx, "Low", 1000, 50, 100)
	if err != nil {
		t.Fatalf("create room: %v", err)
	}

	seat := 0
	sess := AgentSession{
		ID:        NewID(),
		AgentID:   agentID,
		RoomID:    roomID,
		SeatID:    &seat,
		JoinMode:  "random",
		Status:    "waiting",
		ExpiresAt: time.Now().Add(time.Hour),
	}
	if err := st.CreateAgentSession(ctx, sess); err != nil {
		t.Fatalf("create session: %v", err)
	}

	got, err := st.GetAgentSession(ctx, sess.ID)
	if err != nil {
		t.Fatalf("get session: %v", err)
	}
	if got.AgentID != agentID || got.RoomID != roomID {
		t.Fatalf("unexpected session: %+v", got)
	}

	tableID, err := st.CreateTable(ctx, roomID, "active", 50, 100)
	if err != nil {
		t.Fatalf("create table: %v", err)
	}
	if err := st.UpdateAgentSessionMatch(ctx, sess.ID, tableID, seat); err != nil {
		t.Fatalf("update match: %v", err)
	}

	got, err = st.GetAgentSession(ctx, sess.ID)
	if err != nil {
		t.Fatalf("get session after update: %v", err)
	}
	if got.TableID != tableID || got.Status != "active" {
		t.Fatalf("unexpected matched session: %+v", got)
	}

	if err := st.CloseAgentSession(ctx, sess.ID); err != nil {
		t.Fatalf("close session: %v", err)
	}
	got, err = st.GetAgentSession(ctx, sess.ID)
	if err != nil {
		t.Fatalf("get session after close: %v", err)
	}
	if got.Status != "closed" || got.ClosedAt == nil {
		t.Fatalf("session not closed: %+v", got)
	}
}

func TestCreateMatchedTableAndSessions(t *testing.T) {
	st, ctx, cleanup := openStore(t)
	defer cleanup()

	agentA := mustCreateAgent(t, st, ctx, "BotA", "key-a", 10000)
	agentB := mustCreateAgent(t, st, ctx, "BotB", "key-b", 10000)
	roomID, err := st.CreateRoom(ctx, "Low", 1000, 50, 100)
	if err != nil {
		t.Fatalf("create room: %v", err)
	}

	waiting := AgentSession{
		ID:        NewID(),
		AgentID:   agentA,
		RoomID:    roomID,
		JoinMode:  "random",
		Status:    "waiting",
		ExpiresAt: time.Now().Add(time.Hour),
	}
	if err := st.CreateAgentSession(ctx, waiting); err != nil {
		t.Fatalf("create waiting session: %v", err)
	}

	tableID := NewID()
	active := AgentSession{
		ID:        NewID(),
		AgentID:   agentB,
		RoomID:    roomID,
		TableID:   tableID,
		JoinMode:  "random",
		Status:    "active",
		ExpiresAt: time.Now().Add(time.Hour),
	}
	if err := st.CreateMatchedTableAndSessions(ctx, tableID, roomID, 50, 100, waiting.ID, active, 0, 1); err != nil {
		t.Fatalf("create matched table/sessions: %v", err)
	}

	waitingGot, err := st.GetAgentSession(ctx, waiting.ID)
	if err != nil {
		t.Fatalf("get waiting session: %v", err)
	}
	if waitingGot.Status != "active" || waitingGot.TableID != tableID {
		t.Fatalf("waiting session not active: %+v", waitingGot)
	}

	activeGot, err := st.GetAgentSession(ctx, active.ID)
	if err != nil {
		t.Fatalf("get active session: %v", err)
	}
	if activeGot.Status != "active" || activeGot.TableID != tableID {
		t.Fatalf("active session not active: %+v", activeGot)
	}

	tables, err := st.ListTables(ctx, roomID, 10, 0)
	if err != nil {
		t.Fatalf("list tables: %v", err)
	}
	if len(tables) != 1 || tables[0].ID != tableID {
		t.Fatalf("unexpected tables: %+v", tables)
	}
}
