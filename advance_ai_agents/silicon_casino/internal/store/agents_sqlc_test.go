package store

import (
	"errors"
	"testing"
)

func TestAgentsCreateGetListAndNotFound(t *testing.T) {
	st, ctx, cleanup := openStore(t)
	defer cleanup()

	id := mustCreateAgent(t, st, ctx, "A", "key-a", 0)
	_ = id

	a, err := st.GetAgentByAPIKey(ctx, "key-a")
	if err != nil {
		t.Fatalf("get agent by api key: %v", err)
	}
	if a.Name != "A" {
		t.Fatalf("expected name A, got %s", a.Name)
	}

	list, err := st.ListAgents(ctx, 10, 0)
	if err != nil {
		t.Fatalf("list agents: %v", err)
	}
	if len(list) != 1 {
		t.Fatalf("expected 1 agent, got %d", len(list))
	}

	_, err = st.GetAgentByAPIKey(ctx, "missing")
	if !errors.Is(err, ErrNotFound) {
		t.Fatalf("expected ErrNotFound, got %v", err)
	}
}
