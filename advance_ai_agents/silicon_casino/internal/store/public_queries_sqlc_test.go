package store

import (
	"context"
	"testing"
	"time"
)

func TestPublicLeaderboardExcludesTopupAndRanksByPlayResults(t *testing.T) {
	st, ctx, cleanup := openStore(t)
	defer cleanup()

	a1 := mustCreateAgent(t, st, ctx, "A", "key-a", 200000)
	a2 := mustCreateAgent(t, st, ctx, "B", "key-b", 200000)

	roomID, err := st.CreateRoom(ctx, "Low", 1000, 50, 100)
	if err != nil {
		t.Fatalf("create room: %v", err)
	}
	tableID, err := st.CreateTable(ctx, roomID, "active", 50, 100)
	if err != nil {
		t.Fatalf("create table: %v", err)
	}

	_, err = st.Credit(ctx, a1, 1_000_000, "topup_credit", "topup", NewID())
	if err != nil {
		t.Fatalf("topup a1: %v", err)
	}

	for i := 0; i < 220; i++ {
		if err := recordSettledHand(t, st, ctx, tableID, a2, a1, 100); err != nil {
			t.Fatalf("record hand %d: %v", i, err)
		}
	}

	lb, err := st.ListLeaderboard(ctx, LeaderboardFilter{
		RoomScope: "all",
		SortBy:    "score",
	}, 10, 0)
	if err != nil {
		t.Fatalf("list leaderboard: %v", err)
	}
	if len(lb) != 2 {
		t.Fatalf("expected 2 leaderboard entries, got %d", len(lb))
	}
	if lb[0].AgentID != a2 {
		t.Fatalf("expected %s first, got %s", a2, lb[0].AgentID)
	}
	if lb[0].NetCCFromPlay <= 0 {
		t.Fatalf("expected positive net_cc_from_play for winner, got %d", lb[0].NetCCFromPlay)
	}
	if lb[1].NetCCFromPlay >= 0 {
		t.Fatalf("expected negative net_cc_from_play for loser, got %d", lb[1].NetCCFromPlay)
	}
}

func TestPublicLeaderboardRespectsRoomScope(t *testing.T) {
	st, ctx, cleanup := openStore(t)
	defer cleanup()

	a1 := mustCreateAgent(t, st, ctx, "A", "key-a", 200000)
	a2 := mustCreateAgent(t, st, ctx, "B", "key-b", 200000)

	lowRoomID, err := st.CreateRoom(ctx, "Low", 1000, 50, 100)
	if err != nil {
		t.Fatalf("create low room: %v", err)
	}
	midRoomID, err := st.CreateRoom(ctx, "Mid", 5000, 100, 200)
	if err != nil {
		t.Fatalf("create mid room: %v", err)
	}
	lowTableID, err := st.CreateTable(ctx, lowRoomID, "active", 50, 100)
	if err != nil {
		t.Fatalf("create low table: %v", err)
	}
	midTableID, err := st.CreateTable(ctx, midRoomID, "active", 100, 200)
	if err != nil {
		t.Fatalf("create mid table: %v", err)
	}

	for i := 0; i < 3; i++ {
		if err := recordSettledHand(t, st, ctx, lowTableID, a1, a2, 100); err != nil {
			t.Fatalf("record low hand %d: %v", i, err)
		}
	}
	for i := 0; i < 3; i++ {
		if err := recordSettledHand(t, st, ctx, midTableID, a2, a1, 200); err != nil {
			t.Fatalf("record mid hand %d: %v", i, err)
		}
	}

	lbLow, err := st.ListLeaderboard(ctx, LeaderboardFilter{
		RoomScope: "low",
		SortBy:    "score",
	}, 10, 0)
	if err != nil {
		t.Fatalf("list low leaderboard: %v", err)
	}
	if len(lbLow) < 2 || lbLow[0].AgentID != a1 {
		t.Fatalf("expected %s first in low scope", a1)
	}

	lbMid, err := st.ListLeaderboard(ctx, LeaderboardFilter{
		RoomScope: "mid",
		SortBy:    "score",
	}, 10, 0)
	if err != nil {
		t.Fatalf("list mid leaderboard: %v", err)
	}
	if len(lbMid) < 2 || lbMid[0].AgentID != a2 {
		t.Fatalf("expected %s first in mid scope", a2)
	}

}

func TestPublicLeaderboardRespectsWindowStart(t *testing.T) {
	st, ctx, cleanup := openStore(t)
	defer cleanup()

	a1 := mustCreateAgent(t, st, ctx, "A", "key-a", 200000)
	a2 := mustCreateAgent(t, st, ctx, "B", "key-b", 200000)
	roomID, err := st.CreateRoom(ctx, "Low", 1000, 50, 100)
	if err != nil {
		t.Fatalf("create room: %v", err)
	}
	tableID, err := st.CreateTable(ctx, roomID, "active", 50, 100)
	if err != nil {
		t.Fatalf("create table: %v", err)
	}
	for i := 0; i < 4; i++ {
		if err := recordSettledHand(t, st, ctx, tableID, a1, a2, 100); err != nil {
			t.Fatalf("record hand %d: %v", i, err)
		}
	}

	future := time.Now().UTC().Add(1 * time.Hour)
	lbFuture, err := st.ListLeaderboard(ctx, LeaderboardFilter{
		WindowStart: &future,
		RoomScope:   "all",
		SortBy:      "score",
	}, 10, 0)
	if err != nil {
		t.Fatalf("list future-scoped leaderboard: %v", err)
	}
	if len(lbFuture) != 0 {
		t.Fatalf("expected no rows for future window_start, got %d", len(lbFuture))
	}

	lbAll, err := st.ListLeaderboard(ctx, LeaderboardFilter{
		RoomScope: "all",
		SortBy:    "score",
	}, 10, 0)
	if err != nil {
		t.Fatalf("list unscoped leaderboard: %v", err)
	}
	if len(lbAll) == 0 {
		t.Fatal("expected rows when window_start is nil")
	}
}

func TestPublicLeaderboardSortModes(t *testing.T) {
	st, ctx, cleanup := openStore(t)
	defer cleanup()

	a1 := mustCreateAgent(t, st, ctx, "A", "key-a", 400000)
	a2 := mustCreateAgent(t, st, ctx, "B", "key-b", 400000)
	a3 := mustCreateAgent(t, st, ctx, "C", "key-c", 400000)
	roomID, err := st.CreateRoom(ctx, "Low", 1000, 50, 100)
	if err != nil {
		t.Fatalf("create room: %v", err)
	}
	tableID, err := st.CreateTable(ctx, roomID, "active", 50, 100)
	if err != nil {
		t.Fatalf("create table: %v", err)
	}

	// A wins fewer but high-value hands.
	for i := 0; i < 5; i++ {
		if err := recordSettledHand(t, st, ctx, tableID, a1, a2, 400); err != nil {
			t.Fatalf("record A hand %d: %v", i, err)
		}
	}
	// C plays many hands with moderate win rate.
	for i := 0; i < 22; i++ {
		if err := recordSettledHand(t, st, ctx, tableID, a3, a2, 100); err != nil {
			t.Fatalf("record C win hand %d: %v", i, err)
		}
	}
	for i := 0; i < 18; i++ {
		if err := recordSettledHand(t, st, ctx, tableID, a2, a3, 100); err != nil {
			t.Fatalf("record C loss hand %d: %v", i, err)
		}
	}

	lbNet, err := st.ListLeaderboard(ctx, LeaderboardFilter{
		RoomScope: "all",
		SortBy:    "net_cc_from_play",
	}, 10, 0)
	if err != nil {
		t.Fatalf("list net leaderboard: %v", err)
	}
	if len(lbNet) == 0 || lbNet[0].AgentID != a1 {
		t.Fatalf("expected %s first by net_cc_from_play", a1)
	}

	lbHands, err := st.ListLeaderboard(ctx, LeaderboardFilter{
		RoomScope: "all",
		SortBy:    "hands_played",
	}, 10, 0)
	if err != nil {
		t.Fatalf("list hands leaderboard: %v", err)
	}
	if len(lbHands) == 0 || lbHands[0].AgentID != a2 {
		t.Fatalf("expected %s first by hands_played", a2)
	}

	lbWinRate, err := st.ListLeaderboard(ctx, LeaderboardFilter{
		RoomScope: "all",
		SortBy:    "win_rate",
	}, 10, 0)
	if err != nil {
		t.Fatalf("list win_rate leaderboard: %v", err)
	}
	if len(lbWinRate) == 0 || lbWinRate[0].AgentID != a1 {
		t.Fatalf("expected %s first by win_rate", a1)
	}
}

func TestTableHistoryIncludesHumanizedFieldsAndCount(t *testing.T) {
	st, ctx, cleanup := openStore(t)
	defer cleanup()

	a1 := mustCreateAgent(t, st, ctx, "Alpha", "key-alpha", 100000)
	a2 := mustCreateAgent(t, st, ctx, "Bravo", "key-bravo", 100000)

	roomID, err := st.CreateRoom(ctx, "Mid", 5000, 100, 200)
	if err != nil {
		t.Fatalf("create room: %v", err)
	}
	tableID, err := st.CreateTable(ctx, roomID, "closed", 100, 200)
	if err != nil {
		t.Fatalf("create table: %v", err)
	}

	if err := st.CreateAgentSession(ctx, AgentSession{
		ID:        NewID(),
		AgentID:   a1,
		RoomID:    roomID,
		TableID:   tableID,
		JoinMode:  "random",
		Status:    "active",
		ExpiresAt: time.Now().UTC().Add(30 * time.Minute),
	}); err != nil {
		t.Fatalf("create session a1: %v", err)
	}
	if err := st.CreateAgentSession(ctx, AgentSession{
		ID:        NewID(),
		AgentID:   a2,
		RoomID:    roomID,
		TableID:   tableID,
		JoinMode:  "random",
		Status:    "active",
		ExpiresAt: time.Now().UTC().Add(30 * time.Minute),
	}); err != nil {
		t.Fatalf("create session a2: %v", err)
	}

	for i := 0; i < 3; i++ {
		if err := recordSettledHand(t, st, ctx, tableID, a1, a2, 100); err != nil {
			t.Fatalf("record hand %d: %v", i, err)
		}
	}

	total, err := st.CountTableHistoryByScope(ctx, roomID, "")
	if err != nil {
		t.Fatalf("count table history: %v", err)
	}
	if total != 1 {
		t.Fatalf("expected total=1, got %d", total)
	}

	items, err := st.ListTableHistory(ctx, roomID, "", 10, 0)
	if err != nil {
		t.Fatalf("list table history: %v", err)
	}
	if len(items) != 1 {
		t.Fatalf("expected 1 row, got %d", len(items))
	}
	row := items[0]
	if row.RoomName != "Mid" {
		t.Fatalf("expected room name Mid, got %q", row.RoomName)
	}
	if row.HandsPlayed != 3 {
		t.Fatalf("expected hands_played=3, got %d", row.HandsPlayed)
	}
	if len(row.Participants) != 2 {
		t.Fatalf("expected 2 participants, got %d", len(row.Participants))
	}
}

func TestGetAgentPerformanceByWindowAndAgent(t *testing.T) {
	st, ctx, cleanup := openStore(t)
	defer cleanup()

	winner := mustCreateAgent(t, st, ctx, "Winner", "key-winner", 200000)
	loser := mustCreateAgent(t, st, ctx, "Loser", "key-loser", 200000)
	idle := mustCreateAgent(t, st, ctx, "Idle", "key-idle", 200000)

	roomID, err := st.CreateRoom(ctx, "Low", 1000, 50, 100)
	if err != nil {
		t.Fatalf("create room: %v", err)
	}
	tableID, err := st.CreateTable(ctx, roomID, "closed", 50, 100)
	if err != nil {
		t.Fatalf("create table: %v", err)
	}
	for i := 0; i < 3; i++ {
		if err := recordSettledHand(t, st, ctx, tableID, winner, loser, 100); err != nil {
			t.Fatalf("record hand %d: %v", i, err)
		}
	}

	active, err := st.GetAgentPerformanceByWindowAndAgent(ctx, winner, nil)
	if err != nil {
		t.Fatalf("active performance: %v", err)
	}
	if active.HandsPlayed != 3 {
		t.Fatalf("expected 3 hands, got %d", active.HandsPlayed)
	}
	if active.NetCCFromPlay <= 0 {
		t.Fatalf("expected positive net cc, got %d", active.NetCCFromPlay)
	}
	if active.LastActiveAt == nil {
		t.Fatal("expected non-nil last_active_at")
	}

	idleStats, err := st.GetAgentPerformanceByWindowAndAgent(ctx, idle, nil)
	if err != nil {
		t.Fatalf("idle performance: %v", err)
	}
	if idleStats.HandsPlayed != 0 || idleStats.NetCCFromPlay != 0 {
		t.Fatalf("expected zero stats for idle agent, got hands=%d net=%d", idleStats.HandsPlayed, idleStats.NetCCFromPlay)
	}
	if idleStats.LastActiveAt != nil {
		t.Fatalf("expected nil last_active_at for idle agent, got %v", idleStats.LastActiveAt)
	}
}

func recordSettledHand(t *testing.T, st *Store, ctx context.Context, tableID, winnerID, loserID string, amount int64) error {
	t.Helper()

	handID, err := st.CreateHand(ctx, tableID)
	if err != nil {
		return err
	}
	if _, err := st.Debit(ctx, loserID, amount, "bet_debit", "hand", handID); err != nil {
		return err
	}
	if _, err := st.Credit(ctx, winnerID, amount, "pot_credit", "hand", handID); err != nil {
		return err
	}
	pot := amount * 2
	return st.EndHandWithSummary(ctx, handID, winnerID, &pot, "showdown")
}
