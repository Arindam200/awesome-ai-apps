package runtime

import (
	"context"
	"errors"
	"testing"
	"time"
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

	_, err := coord.SubmitAction(context.Background(), actorSession, ActionRequest{
		RequestID: "req_closing",
		TurnID:    turnID,
		Action:    "call",
	})
	if !errors.Is(err, errTableClosing) {
		t.Fatalf("expected errTableClosing, got %v", err)
	}
}
