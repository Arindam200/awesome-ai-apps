package main

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"silicon-casino/internal/config"
	"silicon-casino/internal/store"
	"silicon-casino/internal/testutil"
)

func TestPublicReplayEndpoints(t *testing.T) {
	st, cleanup := testutil.OpenTestStore(t)
	defer cleanup()

	roomID, err := st.CreateRoom(t.Context(), "Replay", 1000, 50, 100)
	if err != nil {
		t.Fatalf("create room: %v", err)
	}
	tableID, err := st.CreateTable(t.Context(), roomID, "active", 50, 100)
	if err != nil {
		t.Fatalf("create table: %v", err)
	}
	agentID, _, _ := createTestAgent(t, st, "ReplayBot")
	handID, err := st.CreateHand(t.Context(), tableID)
	if err != nil {
		t.Fatalf("create hand: %v", err)
	}
	if err := st.CreateAgentSession(t.Context(), store.AgentSession{
		ID:        store.NewID(),
		AgentID:   agentID,
		RoomID:    roomID,
		TableID:   tableID,
		JoinMode:  "select",
		Status:    "active",
		ExpiresAt: time.Now().Add(time.Hour),
	}); err != nil {
		t.Fatalf("create agent session: %v", err)
	}
	var handSeq int32 = 0
	if err := st.InsertTableReplayEvent(t.Context(), tableID, handID, 1, &handSeq, "hand_started", agentID, []byte(`{"street":"preflop","pot_cc":150}`), 1); err != nil {
		t.Fatalf("insert replay event: %v", err)
	}
	if err := st.InsertTableReplaySnapshot(t.Context(), tableID, 1, []byte(`{"street":"preflop","pot_cc":150}`), 1); err != nil {
		t.Fatalf("insert replay snapshot: %v", err)
	}
	pot := int64(150)
	if err := st.EndHandWithSummary(t.Context(), handID, agentID, &pot, "preflop"); err != nil {
		t.Fatalf("end hand summary: %v", err)
	}

	r := newTestRouter(st, config.ServerConfig{})

	t.Run("replay", func(t *testing.T) {
		req := httptest.NewRequest(http.MethodGet, "/api/public/tables/"+tableID+"/replay?from_seq=1&limit=10", nil)
		w := httptest.NewRecorder()
		r.ServeHTTP(w, req)
		if w.Code != http.StatusOK {
			t.Fatalf("expected 200 got %d body=%s", w.Code, w.Body.String())
		}
		var body struct {
			Items []map[string]any `json:"items"`
		}
		if err := json.Unmarshal(w.Body.Bytes(), &body); err != nil {
			t.Fatalf("decode body: %v", err)
		}
		if len(body.Items) == 0 {
			t.Fatalf("expected replay items")
		}
	})

	t.Run("timeline", func(t *testing.T) {
		req := httptest.NewRequest(http.MethodGet, "/api/public/tables/"+tableID+"/timeline", nil)
		w := httptest.NewRecorder()
		r.ServeHTTP(w, req)
		if w.Code != http.StatusOK {
			t.Fatalf("expected 200 got %d body=%s", w.Code, w.Body.String())
		}
	})

	t.Run("snapshot", func(t *testing.T) {
		req := httptest.NewRequest(http.MethodGet, "/api/public/tables/"+tableID+"/snapshot?at_seq=1", nil)
		w := httptest.NewRecorder()
		r.ServeHTTP(w, req)
		if w.Code != http.StatusOK {
			t.Fatalf("expected 200 got %d body=%s", w.Code, w.Body.String())
		}
	})

	t.Run("agent_tables", func(t *testing.T) {
		req := httptest.NewRequest(http.MethodGet, "/api/public/agents/"+agentID+"/tables", nil)
		w := httptest.NewRecorder()
		r.ServeHTTP(w, req)
		if w.Code != http.StatusOK {
			t.Fatalf("expected 200 got %d body=%s", w.Code, w.Body.String())
		}
	})
}
