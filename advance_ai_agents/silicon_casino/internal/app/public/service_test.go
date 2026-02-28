package public

import (
	"errors"
	"testing"
	"time"

	"silicon-casino/internal/store"
	"silicon-casino/internal/testutil"
)

func TestClampLeaderboardPage(t *testing.T) {
	tests := []struct {
		name      string
		limit     int
		offset    int
		wantLimit int
		wantOK    bool
	}{
		{name: "default limit", limit: 0, offset: 0, wantLimit: 50, wantOK: true},
		{name: "explicit small limit", limit: 20, offset: 0, wantLimit: 20, wantOK: true},
		{name: "limit clipped at top100 boundary", limit: 10, offset: 95, wantLimit: 5, wantOK: true},
		{name: "limit exactly remaining", limit: 1, offset: 99, wantLimit: 1, wantOK: true},
		{name: "offset 100 rejected", limit: 10, offset: 100, wantLimit: 0, wantOK: false},
		{name: "offset beyond 100 rejected", limit: 10, offset: 150, wantLimit: 0, wantOK: false},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			gotLimit, gotOK := clampLeaderboardPage(tt.limit, tt.offset)
			if gotOK != tt.wantOK {
				t.Fatalf("ok = %v, want %v", gotOK, tt.wantOK)
			}
			if gotLimit != tt.wantLimit {
				t.Fatalf("limit = %d, want %d", gotLimit, tt.wantLimit)
			}
		})
	}
}

func TestLeaderboardWindowStart(t *testing.T) {
	now := time.Now().UTC()
	tests := []struct {
		name      string
		window    string
		wantNil   bool
		wantRange time.Duration
	}{
		{name: "7d", window: "7d", wantNil: false, wantRange: 7 * 24 * time.Hour},
		{name: "30d", window: "30d", wantNil: false, wantRange: 30 * 24 * time.Hour},
		{name: "all", window: "all", wantNil: true},
		{name: "unknown", window: "x", wantNil: true},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got := leaderboardWindowStart(tt.window)
			if tt.wantNil {
				if got != nil {
					t.Fatalf("expected nil, got %v", *got)
				}
				return
			}
			if got == nil {
				t.Fatal("expected non-nil time")
			}
			diff := now.Sub(*got)
			if diff < tt.wantRange-time.Minute || diff > tt.wantRange+time.Minute {
				t.Fatalf("diff=%v out of expected range around %v", diff, tt.wantRange)
			}
		})
	}
}

func TestTableHistoryIncludesTotalAndSupportsOffsetBeyondTotal(t *testing.T) {
	st, cleanup := testutil.OpenTestStore(t)
	defer cleanup()
	svc := NewService(st)
	ctx := t.Context()

	agentA, err := st.CreateAgent(ctx, "A", "api-a", "claim-a")
	if err != nil {
		t.Fatalf("create agent A: %v", err)
	}
	agentB, err := st.CreateAgent(ctx, "B", "api-b", "claim-b")
	if err != nil {
		t.Fatalf("create agent B: %v", err)
	}
	roomID, err := st.CreateRoom(ctx, "Mid", 5000, 100, 200)
	if err != nil {
		t.Fatalf("create room: %v", err)
	}
	tableID, err := st.CreateTable(ctx, roomID, "closed", 100, 200)
	if err != nil {
		t.Fatalf("create table: %v", err)
	}
	if err := st.CreateAgentSession(ctx, store.AgentSession{
		ID:        store.NewID(),
		AgentID:   agentA,
		RoomID:    roomID,
		TableID:   tableID,
		JoinMode:  "random",
		Status:    "active",
		ExpiresAt: time.Now().UTC().Add(1 * time.Hour),
	}); err != nil {
		t.Fatalf("create session A: %v", err)
	}
	if err := st.CreateAgentSession(ctx, store.AgentSession{
		ID:        store.NewID(),
		AgentID:   agentB,
		RoomID:    roomID,
		TableID:   tableID,
		JoinMode:  "random",
		Status:    "active",
		ExpiresAt: time.Now().UTC().Add(1 * time.Hour),
	}); err != nil {
		t.Fatalf("create session B: %v", err)
	}

	resp, err := svc.TableHistory(ctx, roomID, "", 20, 0)
	if err != nil {
		t.Fatalf("table history: %v", err)
	}
	if resp.Total != 1 {
		t.Fatalf("expected total=1, got %d", resp.Total)
	}
	if len(resp.Items) != 1 {
		t.Fatalf("expected 1 item, got %d", len(resp.Items))
	}

	resp2, err := svc.TableHistory(ctx, roomID, "", 20, 20)
	if err != nil {
		t.Fatalf("table history with high offset: %v", err)
	}
	if resp2.Total != 1 {
		t.Fatalf("expected total still 1, got %d", resp2.Total)
	}
	if len(resp2.Items) != 0 {
		t.Fatalf("expected empty page for high offset, got %d", len(resp2.Items))
	}
}

func TestAgentProfileIncludesStatsAndTables(t *testing.T) {
	st, cleanup := testutil.OpenTestStore(t)
	defer cleanup()
	svc := NewService(st)
	ctx := t.Context()

	agentA, err := st.CreateAgent(ctx, "Alpha", "api-profile-a", "claim-profile-a")
	if err != nil {
		t.Fatalf("create agent A: %v", err)
	}
	agentB, err := st.CreateAgent(ctx, "Bravo", "api-profile-b", "claim-profile-b")
	if err != nil {
		t.Fatalf("create agent B: %v", err)
	}
	roomID, err := st.CreateRoom(ctx, "Low", 1000, 50, 100)
	if err != nil {
		t.Fatalf("create room: %v", err)
	}
	tableID, err := st.CreateTable(ctx, roomID, "closed", 50, 100)
	if err != nil {
		t.Fatalf("create table: %v", err)
	}
	if err := st.CreateAgentSession(ctx, store.AgentSession{
		ID:        store.NewID(),
		AgentID:   agentA,
		RoomID:    roomID,
		TableID:   tableID,
		JoinMode:  "random",
		Status:    "active",
		ExpiresAt: time.Now().UTC().Add(1 * time.Hour),
	}); err != nil {
		t.Fatalf("create session A: %v", err)
	}
	if err := st.CreateAgentSession(ctx, store.AgentSession{
		ID:        store.NewID(),
		AgentID:   agentB,
		RoomID:    roomID,
		TableID:   tableID,
		JoinMode:  "random",
		Status:    "active",
		ExpiresAt: time.Now().UTC().Add(1 * time.Hour),
	}); err != nil {
		t.Fatalf("create session B: %v", err)
	}
	handID, err := st.CreateHand(ctx, tableID)
	if err != nil {
		t.Fatalf("create hand: %v", err)
	}
	if _, err := st.Debit(ctx, agentB, 100, "bet_debit", "hand", handID); err != nil {
		t.Fatalf("debit loser: %v", err)
	}
	if _, err := st.Credit(ctx, agentA, 100, "pot_credit", "hand", handID); err != nil {
		t.Fatalf("credit winner: %v", err)
	}
	pot := int64(200)
	if err := st.EndHandWithSummary(ctx, handID, agentA, &pot, "showdown"); err != nil {
		t.Fatalf("end hand: %v", err)
	}

	resp, err := svc.AgentProfile(ctx, agentA, 20, 0)
	if err != nil {
		t.Fatalf("agent profile: %v", err)
	}
	if resp.Agent.AgentID != agentA {
		t.Fatalf("expected agent_id=%s, got %s", agentA, resp.Agent.AgentID)
	}
	if resp.Stats30D.HandsPlayed <= 0 {
		t.Fatalf("expected stats_30d hands > 0, got %d", resp.Stats30D.HandsPlayed)
	}
	if resp.StatsAll.HandsPlayed <= 0 {
		t.Fatalf("expected stats_all hands > 0, got %d", resp.StatsAll.HandsPlayed)
	}
	if resp.Tables.Total != 1 {
		t.Fatalf("expected tables total=1, got %d", resp.Tables.Total)
	}
	if len(resp.Tables.Items) != 1 {
		t.Fatalf("expected tables items=1, got %d", len(resp.Tables.Items))
	}
}

func TestAgentProfileReturnsZeroStatsWhenNoHands(t *testing.T) {
	st, cleanup := testutil.OpenTestStore(t)
	defer cleanup()
	svc := NewService(st)
	ctx := t.Context()

	agentID, err := st.CreateAgent(ctx, "Idle", "api-idle", "claim-idle")
	if err != nil {
		t.Fatalf("create agent: %v", err)
	}

	resp, err := svc.AgentProfile(ctx, agentID, 20, 0)
	if err != nil {
		t.Fatalf("agent profile: %v", err)
	}
	if resp.Stats30D.HandsPlayed != 0 || resp.StatsAll.HandsPlayed != 0 {
		t.Fatalf("expected zero hands, got stats_30d=%d stats_all=%d", resp.Stats30D.HandsPlayed, resp.StatsAll.HandsPlayed)
	}
	if resp.Tables.Total != 0 || len(resp.Tables.Items) != 0 {
		t.Fatalf("expected no tables, total=%d items=%d", resp.Tables.Total, len(resp.Tables.Items))
	}
}

func TestAgentProfileSupportsPagination(t *testing.T) {
	st, cleanup := testutil.OpenTestStore(t)
	defer cleanup()
	svc := NewService(st)
	ctx := t.Context()

	agentA, err := st.CreateAgent(ctx, "PagerA", "api-pager-a", "claim-pager-a")
	if err != nil {
		t.Fatalf("create agent A: %v", err)
	}
	agentB, err := st.CreateAgent(ctx, "PagerB", "api-pager-b", "claim-pager-b")
	if err != nil {
		t.Fatalf("create agent B: %v", err)
	}
	roomID, err := st.CreateRoom(ctx, "Mid", 5000, 100, 200)
	if err != nil {
		t.Fatalf("create room: %v", err)
	}

	createTableWithSessions := func() {
		t.Helper()
		tableID, err := st.CreateTable(ctx, roomID, "closed", 100, 200)
		if err != nil {
			t.Fatalf("create table: %v", err)
		}
		if err := st.CreateAgentSession(ctx, store.AgentSession{
			ID:        store.NewID(),
			AgentID:   agentA,
			RoomID:    roomID,
			TableID:   tableID,
			JoinMode:  "random",
			Status:    "active",
			ExpiresAt: time.Now().UTC().Add(1 * time.Hour),
		}); err != nil {
			t.Fatalf("create session A: %v", err)
		}
		if err := st.CreateAgentSession(ctx, store.AgentSession{
			ID:        store.NewID(),
			AgentID:   agentB,
			RoomID:    roomID,
			TableID:   tableID,
			JoinMode:  "random",
			Status:    "active",
			ExpiresAt: time.Now().UTC().Add(1 * time.Hour),
		}); err != nil {
			t.Fatalf("create session B: %v", err)
		}
	}
	createTableWithSessions()
	createTableWithSessions()

	page1, err := svc.AgentProfile(ctx, agentA, 1, 0)
	if err != nil {
		t.Fatalf("profile page 1: %v", err)
	}
	page2, err := svc.AgentProfile(ctx, agentA, 1, 1)
	if err != nil {
		t.Fatalf("profile page 2: %v", err)
	}
	if page1.Tables.Total != 2 || page2.Tables.Total != 2 {
		t.Fatalf("expected total=2, got page1=%d page2=%d", page1.Tables.Total, page2.Tables.Total)
	}
	if len(page1.Tables.Items) != 1 || len(page2.Tables.Items) != 1 {
		t.Fatalf("expected 1 item per page, got page1=%d page2=%d", len(page1.Tables.Items), len(page2.Tables.Items))
	}
}

func TestAgentProfileRejectsEmptyAgentID(t *testing.T) {
	st, cleanup := testutil.OpenTestStore(t)
	defer cleanup()
	svc := NewService(st)

	_, err := svc.AgentProfile(t.Context(), "", 20, 0)
	if !errors.Is(err, ErrInvalidRequest) {
		t.Fatalf("expected ErrInvalidRequest, got %v", err)
	}
}
