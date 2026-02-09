package agentgateway

import (
	"bytes"
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/go-chi/chi/v5"
)

func TestReconnectWithinGraceRestoresTableActive(t *testing.T) {
	coord, s1ID, _ := setupMatchedSessions(t)
	prevGrace := reconnectGracePeriod
	reconnectGracePeriod = 200 * time.Millisecond
	defer func() { reconnectGracePeriod = prevGrace }()

	coord.mu.Lock()
	sess := coord.sessions[s1ID]
	agentID := sess.agent.ID
	coord.mu.Unlock()

	if err := coord.CloseSession(context.Background(), s1ID); err != nil {
		t.Fatalf("close session: %v", err)
	}

	res, err := coord.CreateSession(context.Background(), CreateSessionRequest{
		AgentID:  agentID,
		APIKey:   "key-a",
		JoinMode: "random",
	})
	if err != nil {
		t.Fatalf("reconnect create session: %v", err)
	}
	if res.SessionID != s1ID {
		t.Fatalf("expected reconnect to reuse session %s, got %s", s1ID, res.SessionID)
	}

	state, err := coord.GetState(s1ID)
	if err != nil {
		t.Fatalf("get state: %v", err)
	}
	if state.TableStatus != tableStatusActive {
		t.Fatalf("expected table active after reconnect, got %s", state.TableStatus)
	}
}

func TestActionRejectedWhileTableClosing(t *testing.T) {
	coord, s1ID, s2ID := setupMatchedSessions(t)
	prevGrace := reconnectGracePeriod
	reconnectGracePeriod = 200 * time.Millisecond
	defer func() { reconnectGracePeriod = prevGrace }()

	coord.mu.Lock()
	rt := coord.sessions[s1ID].runtime
	turnID := rt.turnID
	actor := rt.engine.State.CurrentActor
	actorSession := s1ID
	nonActorSession := s2ID
	if coord.sessions[s1ID].seat != actor {
		actorSession = s2ID
		nonActorSession = s1ID
	}
	coord.mu.Unlock()

	if err := coord.CloseSession(context.Background(), nonActorSession); err != nil {
		t.Fatalf("close non actor session: %v", err)
	}

	router := chi.NewRouter()
	router.Post("/api/agent/sessions/{session_id}/actions", ActionsHandler(coord))

	body := ActionRequest{RequestID: "req_closing", TurnID: turnID, Action: "call"}
	b, _ := json.Marshal(body)
	req := httptest.NewRequest(http.MethodPost, "/api/agent/sessions/"+actorSession+"/actions", bytes.NewReader(b))
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)
	if w.Code != http.StatusConflict {
		t.Fatalf("expected 409 table_closing got %d body=%s", w.Code, w.Body.String())
	}
}
