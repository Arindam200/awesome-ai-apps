package runtime

import (
	"context"
	"testing"
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

	body := ActionRequest{RequestID: "req_dup", TurnID: turnID, Action: "call"}

	for i := 0; i < 3; i++ {
		if _, err := coord.SubmitAction(context.Background(), actorSession, body); err != nil {
			t.Fatalf("attempt %d: submit action failed: %v", i+1, err)
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
