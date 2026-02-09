package agentgateway

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/go-chi/chi/v5"
)

func TestStateEndpoint(t *testing.T) {
	coord, s1ID, _ := setupMatchedSessions(t)

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
	if _, ok := state["action_constraints"]; !ok {
		t.Fatalf("state missing action_constraints")
	}
	seatsAny, ok := state["seats"].([]any)
	if !ok || len(seatsAny) != 2 {
		t.Fatalf("expected 2 seats, got %#v", state["seats"])
	}
	for _, s := range seatsAny {
		seatMap := s.(map[string]any)
		if _, ok := seatMap["street_contribution"]; !ok {
			t.Fatalf("seat missing street_contribution: %v", seatMap)
		}
		if _, ok := seatMap["to_call"]; !ok {
			t.Fatalf("seat missing to_call: %v", seatMap)
		}
		if _, ok := seatMap["hole_cards"]; ok {
			t.Fatalf("seat should not expose hole_cards: %v", seatMap)
		}
	}

}
