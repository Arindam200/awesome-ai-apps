package agentgateway

import (
	"bufio"
	"bytes"
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strconv"
	"strings"
	"testing"
	"time"

	"github.com/go-chi/chi/v5"
)

type parsedSSE struct {
	ID    string
	Event string
	Data  string
}

func readEventWithTimeout(t *testing.T, rd *bufio.Reader, timeout time.Duration) parsedSSE {
	t.Helper()
	ch := make(chan parsedSSE, 1)
	errCh := make(chan error, 1)
	go func() {
		ev, err := readEvent(rd)
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
	return parsedSSE{}
}

func readEvent(rd *bufio.Reader) (parsedSSE, error) {
	ev := parsedSSE{}
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

func TestEventsSSEReplayOrderAndLastEventID(t *testing.T) {
	coord, s1ID, s2ID := setupMatchedSessions(t)
	router := chi.NewRouter()
	router.Get("/api/agent/sessions/{session_id}/events", EventsSSEHandler(coord))
	router.Post("/api/agent/sessions/{session_id}/actions", ActionsHandler(coord))
	srv := httptest.NewServer(router)
	defer srv.Close()

	req, _ := http.NewRequest(http.MethodGet, srv.URL+"/api/agent/sessions/"+s1ID+"/events", nil)
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatalf("open sse: %v", err)
	}
	defer resp.Body.Close()
	rd := bufio.NewReader(resp.Body)
	ev1 := readEventWithTimeout(t, rd, time.Second)
	ev2 := readEventWithTimeout(t, rd, time.Second)
	id1, _ := strconv.Atoi(ev1.ID)
	id2, _ := strconv.Atoi(ev2.ID)
	if !(id2 > id1) {
		t.Fatalf("event ids not increasing: %s then %s", ev1.ID, ev2.ID)
	}

	coord.mu.Lock()
	rt := coord.sessions[s1ID].runtime
	turnID := rt.turnID
	actor := rt.engine.State.CurrentActor
	actorSession := s1ID
	if coord.sessions[s1ID].seat != actor {
		actorSession = s2ID
	}
	coord.mu.Unlock()

	body := ActionRequest{RequestID: "req_stream", TurnID: turnID, Action: "call"}
	b, _ := json.Marshal(body)
	postReq := httptest.NewRequest(http.MethodPost, "/api/agent/sessions/"+actorSession+"/actions", bytes.NewReader(b))
	postW := httptest.NewRecorder()
	router.ServeHTTP(postW, postReq)
	if postW.Code != http.StatusOK {
		t.Fatalf("post action failed: %d %s", postW.Code, postW.Body.String())
	}
	lastSeen := ev2.ID
	req2, _ := http.NewRequest(http.MethodGet, srv.URL+"/api/agent/sessions/"+s1ID+"/events", nil)
	req2.Header.Set("Last-Event-ID", lastSeen)
	resp2, err := http.DefaultClient.Do(req2)
	if err != nil {
		t.Fatalf("open sse replay: %v", err)
	}
	defer resp2.Body.Close()
	rd2 := bufio.NewReader(resp2.Body)
	ev := readEventWithTimeout(t, rd2, time.Second)
	idNew, _ := strconv.Atoi(ev.ID)
	idOld, _ := strconv.Atoi(lastSeen)
	if !(idNew > idOld) {
		t.Fatalf("expected replay event id > %s, got %s", lastSeen, ev.ID)
	}
}

func TestEventsSSEHeartbeatAndSessionClosed(t *testing.T) {
	prev := ssePingInterval
	ssePingInterval = 20 * time.Millisecond
	defer func() { ssePingInterval = prev }()
	prevGrace := reconnectGracePeriod
	reconnectGracePeriod = 30 * time.Millisecond
	defer func() { reconnectGracePeriod = prevGrace }()

	coord, s1ID, _ := setupMatchedSessions(t)
	router := chi.NewRouter()
	router.Get("/api/agent/sessions/{session_id}/events", EventsSSEHandler(coord))
	srv := httptest.NewServer(router)
	defer srv.Close()

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	req, _ := http.NewRequestWithContext(ctx, http.MethodGet, srv.URL+"/api/agent/sessions/"+s1ID+"/events", nil)
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatalf("open sse: %v", err)
	}
	defer resp.Body.Close()
	rd := bufio.NewReader(resp.Body)

	// Drain initial replay event(s) quickly and wait for ping.
	var sawPing bool
	for i := 0; i < 10; i++ {
		ev := readEventWithTimeout(t, rd, time.Second)
		if ev.Event == "ping" {
			sawPing = true
			break
		}
	}
	if !sawPing {
		t.Fatal("expected ping event")
	}

	if err := coord.CloseSession(context.Background(), s1ID); err != nil {
		t.Fatalf("close session: %v", err)
	}
	var sawGrace bool
	for i := 0; i < 10; i++ {
		ev := readEventWithTimeout(t, rd, time.Second)
		if ev.Event == "reconnect_grace_started" {
			sawGrace = true
			break
		}
	}
	if !sawGrace {
		t.Fatal("expected reconnect_grace_started event")
	}
	time.Sleep(50 * time.Millisecond)
	coord.sweepTableTransitions(context.Background(), time.Now())
	var sawClosed bool
	for i := 0; i < 20; i++ {
		ev := readEventWithTimeout(t, rd, time.Second)
		if ev.Event == "session_closed" {
			sawClosed = true
			break
		}
	}
	if !sawClosed {
		t.Fatal("expected session_closed event after grace timeout")
	}
}

func TestEventsSSEHeaders(t *testing.T) {
	coord, s1ID, _ := setupMatchedSessions(t)
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
	if v := resp.Header.Get("X-Accel-Buffering"); v != "no" {
		t.Fatalf("expected X-Accel-Buffering no, got %q", v)
	}
	if v := resp.Header.Get("X-Content-Type-Options"); v != "nosniff" {
		t.Fatalf("expected X-Content-Type-Options nosniff, got %q", v)
	}
}

func TestEventsSSEUsesStoredOffsetWhenHeaderMissing(t *testing.T) {
	coord, s1ID, s2ID := setupMatchedSessions(t)
	router := chi.NewRouter()
	router.Get("/api/agent/sessions/{session_id}/events", EventsSSEHandler(coord))
	router.Post("/api/agent/sessions/{session_id}/actions", ActionsHandler(coord))
	srv := httptest.NewServer(router)
	defer srv.Close()

	req, _ := http.NewRequest(http.MethodGet, srv.URL+"/api/agent/sessions/"+s1ID+"/events", nil)
	req.Header.Set("Accept", "text/event-stream")
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatalf("open sse: %v", err)
	}
	rd := bufio.NewReader(resp.Body)
	ev1 := readEventWithTimeout(t, rd, time.Second)
	ev2 := readEventWithTimeout(t, rd, time.Second)
	lastSeen := ev2.ID
	resp.Body.Close()

	coord.mu.Lock()
	rt := coord.sessions[s1ID].runtime
	turnID := rt.turnID
	actor := rt.engine.State.CurrentActor
	actorSession := s1ID
	if coord.sessions[s1ID].seat != actor {
		actorSession = s2ID
	}
	coord.mu.Unlock()

	req2, _ := http.NewRequest(http.MethodGet, srv.URL+"/api/agent/sessions/"+s1ID+"/events", nil)
	req2.Header.Set("Accept", "text/event-stream")
	resp2, err := http.DefaultClient.Do(req2)
	if err != nil {
		t.Fatalf("open sse replay: %v", err)
	}
	defer resp2.Body.Close()

	body := ActionRequest{RequestID: "req_offset", TurnID: turnID, Action: "call"}
	b, _ := json.Marshal(body)
	postReq := httptest.NewRequest(http.MethodPost, "/api/agent/sessions/"+actorSession+"/actions", bytes.NewReader(b))
	postW := httptest.NewRecorder()
	router.ServeHTTP(postW, postReq)
	if postW.Code != http.StatusOK {
		t.Fatalf("post action failed: %d %s", postW.Code, postW.Body.String())
	}

	rd2 := bufio.NewReader(resp2.Body)
	ev := readEventWithTimeout(t, rd2, time.Second)
	idNew, _ := strconv.Atoi(ev.ID)
	idOld, _ := strconv.Atoi(lastSeen)
	if !(idNew > idOld) {
		t.Fatalf("expected event id > %s, got %s (ev1=%s)", lastSeen, ev.ID, ev1.ID)
	}
}

func TestEventsSSEInvalidLastEventIDReplaysBuffer(t *testing.T) {
	coord, s1ID, _ := setupMatchedSessions(t)
	router := chi.NewRouter()
	router.Get("/api/agent/sessions/{session_id}/events", EventsSSEHandler(coord))
	srv := httptest.NewServer(router)
	defer srv.Close()

	req, _ := http.NewRequest(http.MethodGet, srv.URL+"/api/agent/sessions/"+s1ID+"/events", nil)
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatalf("open sse: %v", err)
	}
	rd := bufio.NewReader(resp.Body)
	ev1 := readEventWithTimeout(t, rd, time.Second)
	resp.Body.Close()

	req2, _ := http.NewRequest(http.MethodGet, srv.URL+"/api/agent/sessions/"+s1ID+"/events", nil)
	req2.Header.Set("Last-Event-ID", "not-a-number")
	resp2, err := http.DefaultClient.Do(req2)
	if err != nil {
		t.Fatalf("open sse replay: %v", err)
	}
	defer resp2.Body.Close()
	rd2 := bufio.NewReader(resp2.Body)
	ev2 := readEventWithTimeout(t, rd2, time.Second)
	if ev2.ID != ev1.ID {
		t.Fatalf("expected replay to start from first buffered event %s, got %s", ev1.ID, ev2.ID)
	}
}

func TestSSEEventDataContract(t *testing.T) {
	coord, s1ID, _ := setupMatchedSessions(t)
	router := chi.NewRouter()
	router.Get("/api/agent/sessions/{session_id}/events", EventsSSEHandler(coord))
	srv := httptest.NewServer(router)
	defer srv.Close()

	req, _ := http.NewRequest(http.MethodGet, srv.URL+"/api/agent/sessions/"+s1ID+"/events", nil)
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatalf("open sse: %v", err)
	}
	defer resp.Body.Close()

	rd := bufio.NewReader(resp.Body)
	ev := readEventWithTimeout(t, rd, time.Second)

	var payload struct {
		EventID   string         `json:"event_id"`
		Event     string         `json:"event"`
		SessionID string         `json:"session_id"`
		ServerTS  int64          `json:"server_ts"`
		Data      map[string]any `json:"data"`
	}
	if err := json.Unmarshal([]byte(ev.Data), &payload); err != nil {
		t.Fatalf("decode event data: %v", err)
	}
	if payload.EventID == "" || payload.Event == "" || payload.SessionID == "" {
		t.Fatalf("missing required event fields: %+v", payload)
	}
	if payload.ServerTS == 0 {
		t.Fatal("expected server_ts to be set")
	}
}
