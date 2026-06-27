package httptransport

import (
	"bufio"
	"bytes"
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"silicon-casino/internal/agentgateway"
	"silicon-casino/internal/ledger"
	"silicon-casino/internal/testutil"

	"github.com/go-chi/chi/v5"
)

func TestSessionsCreateAndDelete(t *testing.T) {
	st, cleanup := testutil.OpenTestStore(t)
	defer cleanup()
	ctx := context.Background()
	coord := agentgateway.NewCoordinator(st, ledger.New(st))

	agentID, err := st.CreateAgent(ctx, "bot-a", "api-key-a", "claim-api-key-a")
	if err != nil {
		t.Fatalf("create agent: %v", err)
	}
	if err := st.EnsureAccount(ctx, agentID, 10000); err != nil {
		t.Fatalf("ensure account: %v", err)
	}
	if err := st.EnsureDefaultRooms(ctx); err != nil {
		t.Fatalf("ensure default rooms: %v", err)
	}

	router := chi.NewRouter()
	router.Post("/api/agent/sessions", SessionsCreateHandler(coord))
	router.Delete("/api/agent/sessions/{session_id}", SessionsDeleteHandler(coord))

	body, _ := json.Marshal(agentgateway.CreateSessionRequest{
		AgentID:  agentID,
		APIKey:   "api-key-a",
		JoinMode: "random",
	})
	req := httptest.NewRequest(http.MethodPost, "/api/agent/sessions", bytes.NewReader(body))
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)
	if w.Code != http.StatusOK {
		t.Fatalf("create status=%d body=%s", w.Code, w.Body.String())
	}
	var created agentgateway.CreateSessionResponse
	if err := json.Unmarshal(w.Body.Bytes(), &created); err != nil {
		t.Fatalf("decode create response: %v", err)
	}
	if created.SessionID == "" {
		t.Fatal("session_id should not be empty")
	}

	req = httptest.NewRequest(http.MethodDelete, "/api/agent/sessions/"+created.SessionID, nil)
	w = httptest.NewRecorder()
	router.ServeHTTP(w, req)
	if w.Code != http.StatusOK {
		t.Fatalf("delete status=%d body=%s", w.Code, w.Body.String())
	}
}

func TestActionsAcceptedAndIdempotent(t *testing.T) {
	coord, s1ID, s2ID := setupMatchedSessionsHTTP(t)
	state, err := coord.GetState(s1ID)
	if err != nil {
		t.Fatalf("get state: %v", err)
	}
	reqBody := agentgateway.ActionRequest{
		RequestID: "req_1",
		TurnID:    state.TurnID,
		Action:    "call",
	}

	router := chi.NewRouter()
	router.Post("/api/agent/sessions/{session_id}/actions", ActionsHandler(coord))

	body, _ := json.Marshal(reqBody)
	code := postActionStatus(t, router, s1ID, body)
	actorSession := s1ID
	if code != http.StatusOK {
		code = postActionStatus(t, router, s2ID, body)
		actorSession = s2ID
	}
	if code != http.StatusOK {
		t.Fatalf("expected one actor request to succeed, got last status=%d", code)
	}

	code = postActionStatus(t, router, actorSession, body)
	if code != http.StatusOK {
		t.Fatalf("idempotent request expected 200, got %d", code)
	}
}

func TestStateEndpoint(t *testing.T) {
	coord, s1ID, _ := setupMatchedSessionsHTTP(t)

	router := chi.NewRouter()
	router.Get("/api/agent/sessions/{session_id}/state", StateHandler(coord))

	req := httptest.NewRequest(http.MethodGet, "/api/agent/sessions/"+s1ID+"/state", nil)
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)
	if w.Code != http.StatusOK {
		t.Fatalf("state expected 200 got %d body=%s", w.Code, w.Body.String())
	}
	var state map[string]any
	if err := json.Unmarshal(w.Body.Bytes(), &state); err != nil {
		t.Fatalf("decode state: %v", err)
	}
	if _, ok := state["my_hole_cards"]; !ok {
		t.Fatalf("state missing my_hole_cards: %v", state)
	}
	if _, ok := state["community_cards"]; !ok {
		t.Fatalf("state missing community_cards")
	}
	if _, ok := state["legal_actions"]; !ok {
		t.Fatalf("state missing legal_actions")
	}
}

func TestEventsSSEHeaders(t *testing.T) {
	coord, s1ID, _ := setupMatchedSessionsHTTP(t)
	router := chi.NewRouter()
	router.Get("/api/agent/sessions/{session_id}/events", EventsSSEHandler(coord))
	srv := httptest.NewServer(router)
	defer srv.Close()

	req, _ := http.NewRequest(http.MethodGet, srv.URL+"/api/agent/sessions/"+s1ID+"/events", nil)
	req.Header.Set("Accept", "text/event-stream")
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatalf("open sse: %v", err)
	}
	defer resp.Body.Close()

	if ct := resp.Header.Get("Content-Type"); ct != "text/event-stream" {
		t.Fatalf("expected Content-Type text/event-stream, got %q", ct)
	}
	cc := resp.Header.Get("Cache-Control")
	if !strings.Contains(cc, "no-cache") || !strings.Contains(cc, "no-transform") {
		t.Fatalf("expected Cache-Control to include no-cache and no-transform, got %q", cc)
	}
	event := readSSEEventWithTimeout(t, bufio.NewReader(resp.Body), time.Second)
	if event.ID == "" {
		t.Fatalf("expected first event id, got %+v", event)
	}
}

func setupMatchedSessionsHTTP(t *testing.T) (*agentgateway.Coordinator, string, string) {
	t.Helper()
	st, cleanup := testutil.OpenTestStore(t)
	t.Cleanup(cleanup)
	ctx := context.Background()

	if err := st.EnsureDefaultRooms(ctx); err != nil {
		t.Fatalf("ensure rooms: %v", err)
	}
	a1, err := st.CreateAgent(ctx, "bot-a", "key-a", "claim-key-a")
	if err != nil {
		t.Fatalf("create a1: %v", err)
	}
	a2, err := st.CreateAgent(ctx, "bot-b", "key-b", "claim-key-b")
	if err != nil {
		t.Fatalf("create a2: %v", err)
	}
	if err := st.EnsureAccount(ctx, a1, 100000); err != nil {
		t.Fatalf("ensure account a1: %v", err)
	}
	if err := st.EnsureAccount(ctx, a2, 100000); err != nil {
		t.Fatalf("ensure account a2: %v", err)
	}

	coord := agentgateway.NewCoordinator(st, ledger.New(st))
	if _, err := coord.CreateSession(ctx, agentgateway.CreateSessionRequest{
		AgentID:  a1,
		APIKey:   "key-a",
		JoinMode: "random",
	}); err != nil {
		t.Fatalf("create session 1: %v", err)
	}
	s2, err := coord.CreateSession(ctx, agentgateway.CreateSessionRequest{
		AgentID:  a2,
		APIKey:   "key-b",
		JoinMode: "random",
	})
	if err != nil {
		t.Fatalf("create session 2: %v", err)
	}
	s1, ok := coord.FindOpenSessionByAgent(a1)
	if !ok {
		t.Fatalf("session for agent %s not found", a1)
	}
	return coord, s1.SessionID, s2.SessionID
}

func postActionStatus(t *testing.T, router http.Handler, sessionID string, body []byte) int {
	t.Helper()
	req := httptest.NewRequest(http.MethodPost, "/api/agent/sessions/"+sessionID+"/actions", bytes.NewReader(body))
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)
	return w.Code
}

type sseEvent struct {
	ID    string
	Event string
	Data  string
}

func readSSEEventWithTimeout(t *testing.T, rd *bufio.Reader, timeout time.Duration) sseEvent {
	t.Helper()
	ch := make(chan sseEvent, 1)
	errCh := make(chan error, 1)
	go func() {
		ev, err := readSSEEvent(rd)
		if err != nil {
			errCh <- err
			return
		}
		ch <- ev
	}()
	select {
	case ev := <-ch:
		return ev
	case err := <-errCh:
		t.Fatalf("read event: %v", err)
	case <-time.After(timeout):
		t.Fatal("timeout waiting for sse event")
	}
	return sseEvent{}
}

func readSSEEvent(rd *bufio.Reader) (sseEvent, error) {
	ev := sseEvent{}
	for {
		line, err := rd.ReadString('\n')
		if err != nil {
			return ev, err
		}
		line = strings.TrimRight(line, "\n")
		if line == "" {
			return ev, nil
		}
		if strings.HasPrefix(line, "id: ") {
			ev.ID = strings.TrimPrefix(line, "id: ")
		}
		if strings.HasPrefix(line, "event: ") {
			ev.Event = strings.TrimPrefix(line, "event: ")
		}
		if strings.HasPrefix(line, "data: ") {
			ev.Data = strings.TrimPrefix(line, "data: ")
		}
	}
}
