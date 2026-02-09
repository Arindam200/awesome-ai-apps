package agentgateway

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/go-chi/chi/v5"
)

func TestIdempotencySingleRowForDuplicateRequest(t *testing.T) {
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
	body := ActionRequest{RequestID: "req_dup", TurnID: turnID, Action: "call"}
	b, _ := json.Marshal(body)

	for i := 0; i < 3; i++ {
		req := httptest.NewRequest(http.MethodPost, "/api/agent/sessions/"+actorSession+"/actions", bytes.NewReader(b))
		w := httptest.NewRecorder()
		router.ServeHTTP(w, req)
		if w.Code != http.StatusOK {
			t.Fatalf("attempt %d: expected 200 got %d body=%s", i+1, w.Code, w.Body.String())
		}
	}

	count, err := coord.store.CountAgentActionRequestsBySessionAndRequest(t.Context(), actorSession, "req_dup")
	if err != nil {
		t.Fatalf("count action requests: %v", err)
	}
	if count != 1 {
		t.Fatalf("expected 1 row, got %d", count)
	}
}
