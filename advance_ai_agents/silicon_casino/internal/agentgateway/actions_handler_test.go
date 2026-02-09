package agentgateway

import (
	"bytes"
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"silicon-casino/internal/ledger"
	"silicon-casino/internal/testutil"

	"github.com/go-chi/chi/v5"
)

func setupMatchedSessions(t *testing.T) (*Coordinator, string, string) {
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
	coord := NewCoordinator(st, ledger.New(st))
	if _, err := coord.CreateSession(ctx, CreateSessionRequest{AgentID: a1, APIKey: "key-a", JoinMode: "random"}); err != nil {
		t.Fatalf("create session 1: %v", err)
	}
	s2, err := coord.CreateSession(ctx, CreateSessionRequest{AgentID: a2, APIKey: "key-b", JoinMode: "random"})
	if err != nil {
		t.Fatalf("create session 2: %v", err)
	}
	var s1ID string
	coord.mu.Lock()
	for id, sess := range coord.sessions {
		if sess.agent.ID == a1 {
			s1ID = id
		}
	}
	coord.mu.Unlock()
	return coord, s1ID, s2.SessionID
}

func TestActionsAcceptedAndIdempotent(t *testing.T) {
	coord, s1ID, s2ID := setupMatchedSessions(t)
	coord.mu.Lock()
	rt := coord.sessions[s1ID].runtime
	turnID := rt.turnID
	actor := rt.engine.State.CurrentActor
	var actorSession string
	if coord.sessions[s1ID].seat == actor {
		actorSession = s1ID
	} else {
		actorSession = s2ID
	}
	coord.mu.Unlock()

	router := chi.NewRouter()
	router.Post("/api/agent/sessions/{session_id}/actions", ActionsHandler(coord))
	body := ActionRequest{RequestID: "req_1", TurnID: turnID, Action: "call"}
	b, _ := json.Marshal(body)

	req := httptest.NewRequest(http.MethodPost, "/api/agent/sessions/"+actorSession+"/actions", bytes.NewReader(b))
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)
	if w.Code != http.StatusOK {
		t.Fatalf("expected 200 got %d body=%s", w.Code, w.Body.String())
	}

	req = httptest.NewRequest(http.MethodPost, "/api/agent/sessions/"+actorSession+"/actions", bytes.NewReader(b))
	w = httptest.NewRecorder()
	router.ServeHTTP(w, req)
	if w.Code != http.StatusOK {
		t.Fatalf("idempotent expected 200 got %d body=%s", w.Code, w.Body.String())
	}
}

func TestActionsNotYourTurnAndInvalidTurnID(t *testing.T) {
	coord, s1ID, s2ID := setupMatchedSessions(t)
	coord.mu.Lock()
	rt := coord.sessions[s1ID].runtime
	turnID := rt.turnID
	actor := rt.engine.State.CurrentActor
	var nonActorSession string
	if coord.sessions[s1ID].seat != actor {
		nonActorSession = s1ID
	} else {
		nonActorSession = s2ID
	}
	coord.mu.Unlock()

	router := chi.NewRouter()
	router.Post("/api/agent/sessions/{session_id}/actions", ActionsHandler(coord))

	body := ActionRequest{RequestID: "req_bad_turn", TurnID: "wrong_turn", Action: "call"}
	b, _ := json.Marshal(body)
	req := httptest.NewRequest(http.MethodPost, "/api/agent/sessions/"+nonActorSession+"/actions", bytes.NewReader(b))
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)
	if w.Code != http.StatusBadRequest {
		t.Fatalf("invalid turn expected 400 got %d", w.Code)
	}

	body = ActionRequest{RequestID: "req_not_turn", TurnID: turnID, Action: "call"}
	b, _ = json.Marshal(body)
	req = httptest.NewRequest(http.MethodPost, "/api/agent/sessions/"+nonActorSession+"/actions", bytes.NewReader(b))
	w = httptest.NewRecorder()
	router.ServeHTTP(w, req)
	if w.Code != http.StatusBadRequest {
		t.Fatalf("not your turn expected 400 got %d", w.Code)
	}
}

func TestActionsRaiseMissingAmountRejected(t *testing.T) {
	coord, s1ID, s2ID := setupMatchedSessions(t)
	coord.mu.Lock()
	rt := coord.sessions[s1ID].runtime
	turnID := rt.turnID
	actor := rt.engine.State.CurrentActor
	var actorSession string
	if coord.sessions[s1ID].seat == actor {
		actorSession = s1ID
	} else {
		actorSession = s2ID
	}
	coord.mu.Unlock()

	router := chi.NewRouter()
	router.Post("/api/agent/sessions/{session_id}/actions", ActionsHandler(coord))
	body := ActionRequest{RequestID: "req_raise", TurnID: turnID, Action: "raise"}
	b, _ := json.Marshal(body)
	req := httptest.NewRequest(http.MethodPost, "/api/agent/sessions/"+actorSession+"/actions", bytes.NewReader(b))
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)
	if w.Code != http.StatusBadRequest {
		t.Fatalf("expected 400 got %d body=%s", w.Code, w.Body.String())
	}
}
