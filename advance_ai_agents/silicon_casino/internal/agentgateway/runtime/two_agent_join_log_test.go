package runtime

import (
	"context"
	"testing"

	"silicon-casino/internal/ledger"
	"silicon-casino/internal/testutil"
)

func TestTwoAgentsJoinRoomAndEmitExpectedEvents(t *testing.T) {
	st, cleanup := testutil.OpenTestStore(t)
	defer cleanup()
	ctx := context.Background()

	if err := st.EnsureDefaultRooms(ctx); err != nil {
		t.Fatalf("ensure default rooms: %v", err)
	}
	a1, err := st.CreateAgent(ctx, "join-bot-a", "join-key-a", "claim-join-key-a")
	if err != nil {
		t.Fatalf("create agent a1: %v", err)
	}
	a2, err := st.CreateAgent(ctx, "join-bot-b", "join-key-b", "claim-join-key-b")
	if err != nil {
		t.Fatalf("create agent a2: %v", err)
	}
	if err := st.EnsureAccount(ctx, a1, 100000); err != nil {
		t.Fatalf("ensure account a1: %v", err)
	}
	if err := st.EnsureAccount(ctx, a2, 100000); err != nil {
		t.Fatalf("ensure account a2: %v", err)
	}

	coord := NewCoordinator(st, ledger.New(st))
	s1, err := coord.CreateSession(ctx, CreateSessionRequest{
		AgentID:  a1,
		APIKey:   "join-key-a",
		JoinMode: "random",
	})
	if err != nil {
		t.Fatalf("create session 1: %v", err)
	}
	s2, err := coord.CreateSession(ctx, CreateSessionRequest{
		AgentID:  a2,
		APIKey:   "join-key-b",
		JoinMode: "random",
	})
	if err != nil {
		t.Fatalf("create session 2: %v", err)
	}

	events1 := collectNonPingBufferEvents(t, coord.GetSessionBuffer(s1.SessionID), 4)
	events2 := collectNonPingBufferEvents(t, coord.GetSessionBuffer(s2.SessionID), 3)

	log1 := eventNames(events1)
	log2 := eventNames(events2)
	t.Logf("session %s event log: %v", s1.SessionID, log1)
	t.Logf("session %s event log: %v", s2.SessionID, log2)

	assertContainsInOrder(t, log1, []string{"session_joined", "session_joined", "state_snapshot", "turn_started"})
	assertContainsInOrder(t, log2, []string{"session_joined", "state_snapshot", "turn_started"})

	for _, ev := range append(events1, events2...) {
		if ev.Event == "ping" {
			continue
		}
		if ev.EventID == "" {
			t.Fatalf("expected non-empty event id for event=%s data=%v", ev.Event, ev.Data)
		}
	}

	foundTurnStarted := false
	for _, ev := range append(events1, events2...) {
		if ev.Event != "turn_started" {
			continue
		}
		foundTurnStarted = true
		payload, ok := ev.Data.(map[string]any)
		if !ok {
			t.Fatalf("turn_started payload should be an object, got %T", ev.Data)
		}
		actions := normalizeActions(payload["allowed_actions"])
		if containsAction(actions, "check") || containsAction(actions, "bet") {
			t.Fatalf("preflop opening action set should not include check/bet: %+v", actions)
		}
		if !containsAction(actions, "fold") || !containsAction(actions, "call") || !containsAction(actions, "raise") {
			t.Fatalf("preflop opening action set missing expected actions: %+v", actions)
		}
	}
	if !foundTurnStarted {
		t.Fatal("expected at least one turn_started event")
	}
}

func collectNonPingBufferEvents(t *testing.T, buf *EventBuffer, want int) []StreamEvent {
	t.Helper()
	if buf == nil {
		t.Fatal("session buffer should not be nil")
	}
	all := buf.ReplayAfter("")
	out := make([]StreamEvent, 0, want)
	for _, ev := range all {
		if ev.Event == "ping" {
			continue
		}
		out = append(out, ev)
		if len(out) == want {
			break
		}
	}
	if len(out) < want {
		t.Fatalf("unexpected event count: got=%d want=%d all=%d", len(out), want, len(all))
	}
	return out
}

func eventNames(events []StreamEvent) []string {
	out := make([]string, 0, len(events))
	for _, ev := range events {
		out = append(out, ev.Event)
	}
	return out
}

func assertContainsInOrder(t *testing.T, got []string, expected []string) {
	t.Helper()
	if len(got) < len(expected) {
		t.Fatalf("event count too small: got=%v expected prefix=%v", got, expected)
	}
	j := 0
	for _, v := range got {
		if v == expected[j] {
			j++
			if j == len(expected) {
				return
			}
		}
	}
	t.Fatalf("event order mismatch: got=%v expected(in order)=%v", got, expected)
}

func normalizeActions(raw any) []string {
	switch actions := raw.(type) {
	case []string:
		return actions
	case []any:
		out := make([]string, 0, len(actions))
		for _, v := range actions {
			s, ok := v.(string)
			if ok {
				out = append(out, s)
			}
		}
		return out
	default:
		return nil
	}
}

func containsAction(actions []string, target string) bool {
	for _, action := range actions {
		if action == target {
			return true
		}
	}
	return false
}
