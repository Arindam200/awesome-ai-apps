package agentgateway

import (
	"context"
	"testing"
	"time"
)

func TestExpireSessionsClosesExpired(t *testing.T) {
	coord, s1ID, s2ID := setupMatchedSessions(t)
	prevGrace := reconnectGracePeriod
	reconnectGracePeriod = 20 * time.Millisecond
	defer func() { reconnectGracePeriod = prevGrace }()

	coord.mu.Lock()
	coord.sessions[s1ID].session.ExpiresAt = time.Now().Add(-time.Minute)
	coord.sessions[s2ID].session.ExpiresAt = time.Now().Add(time.Hour)
	coord.mu.Unlock()

	n := coord.expireSessions(context.Background(), time.Now())
	if n != 1 {
		t.Fatalf("expected 1 expired session, got %d", n)
	}

	time.Sleep(40 * time.Millisecond)
	coord.sweepTableTransitions(context.Background(), time.Now())

	sess, err := coord.store.GetAgentSession(context.Background(), s1ID)
	if err != nil {
		t.Fatalf("get agent session: %v", err)
	}
	if sess.Status != "closed" {
		t.Fatalf("expected session status closed, got %s", sess.Status)
	}
}
