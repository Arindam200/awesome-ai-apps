package agentgateway

import (
	"bufio"
	"bytes"
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"silicon-casino/internal/ledger"
	"silicon-casino/internal/testutil"

	"github.com/go-chi/chi/v5"
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
	router := chi.NewRouter()
	router.Post("/api/agent/sessions", SessionsCreateHandler(coord))
	router.Get("/api/agent/sessions/{session_id}/events", EventsSSEHandler(coord))
	srv := httptest.NewServer(router)
	defer srv.Close()

	s1 := createSessionForTest(t, srv.URL, CreateSessionRequest{
		AgentID:  a1,
		APIKey:   "join-key-a",
		JoinMode: "random",
	})
	s2 := createSessionForTest(t, srv.URL, CreateSessionRequest{
		AgentID:  a2,
		APIKey:   "join-key-b",
		JoinMode: "random",
	})

	events1 := collectNonPingEvents(t, srv.URL+"/api/agent/sessions/"+s1.SessionID+"/events", 4)
	events2 := collectNonPingEvents(t, srv.URL+"/api/agent/sessions/"+s2.SessionID+"/events", 3)

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
		if ev.ID == "" {
			t.Fatalf("expected non-empty event id for event=%s data=%s", ev.Event, ev.Data)
		}
	}

	foundTurnStarted := false
	for _, ev := range append(events1, events2...) {
		if ev.Event != "turn_started" {
			continue
		}
		foundTurnStarted = true
		var payload map[string]any
		if err := json.Unmarshal([]byte(ev.Data), &payload); err != nil {
			t.Fatalf("decode turn_started payload: %v", err)
		}
		actionsAny, ok := payload["allowed_actions"].([]any)
		if !ok {
			t.Fatalf("turn_started missing allowed_actions: %v", payload)
		}
		actions := make([]string, 0, len(actionsAny))
		for _, v := range actionsAny {
			s, ok := v.(string)
			if ok {
				actions = append(actions, s)
			}
		}
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

func createSessionForTest(t *testing.T, baseURL string, reqBody CreateSessionRequest) CreateSessionResponse {
	t.Helper()
	payload, err := json.Marshal(reqBody)
	if err != nil {
		t.Fatalf("marshal create session: %v", err)
	}
	req, err := http.NewRequest(http.MethodPost, baseURL+"/api/agent/sessions", bytes.NewReader(payload))
	if err != nil {
		t.Fatalf("build create session request: %v", err)
	}
	req.Header.Set("Content-Type", "application/json")
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatalf("create session request failed: %v", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		var body map[string]any
		_ = json.NewDecoder(resp.Body).Decode(&body)
		t.Fatalf("create session expected 200 got %d body=%v", resp.StatusCode, body)
	}

	var out CreateSessionResponse
	if err := json.NewDecoder(resp.Body).Decode(&out); err != nil {
		t.Fatalf("decode create session response: %v", err)
	}
	if out.SessionID == "" {
		t.Fatal("create session returned empty session_id")
	}
	return out
}

func collectNonPingEvents(t *testing.T, streamURL string, want int) []parsedSSE {
	t.Helper()
	req, err := http.NewRequest(http.MethodGet, streamURL, nil)
	if err != nil {
		t.Fatalf("build sse request: %v", err)
	}
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatalf("open sse stream: %v", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		t.Fatalf("sse expected 200 got %d", resp.StatusCode)
	}

	rd := bufio.NewReader(resp.Body)
	events := make([]parsedSSE, 0, want)
	deadline := time.Now().Add(2 * time.Second)
	for len(events) < want {
		if time.Now().After(deadline) {
			t.Fatalf("timeout collecting non-ping events, got=%d want=%d", len(events), want)
		}
		ev := readEventWithTimeout(t, rd, 500*time.Millisecond)
		if ev.Event == "ping" {
			continue
		}
		events = append(events, ev)
	}
	return events
}

func eventNames(events []parsedSSE) []string {
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

func containsAction(actions []string, target string) bool {
	for _, action := range actions {
		if action == target {
			return true
		}
	}
	return false
}
