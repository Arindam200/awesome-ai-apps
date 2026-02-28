package main

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"silicon-casino/internal/config"
	"silicon-casino/internal/testutil"
)

func TestPublicEndpoints(t *testing.T) {
	st, cleanup := testutil.OpenTestStore(t)
	defer cleanup()
	if err := st.EnsureDefaultRooms(t.Context()); err != nil {
		t.Fatalf("ensure rooms: %v", err)
	}
	router := newTestRouter(st, config.ServerConfig{})

	req := httptest.NewRequest(http.MethodGet, "/api/public/rooms", nil)
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)
	if w.Code != http.StatusOK {
		t.Fatalf("rooms expected 200, got %d", w.Code)
	}
	var roomsResp struct {
		Items []any `json:"items"`
	}
	if err := json.NewDecoder(w.Body).Decode(&roomsResp); err != nil {
		t.Fatalf("decode rooms: %v", err)
	}
	if len(roomsResp.Items) == 0 {
		t.Fatal("expected non-empty rooms")
	}

	req = httptest.NewRequest(http.MethodGet, "/api/public/tables", nil)
	w = httptest.NewRecorder()
	router.ServeHTTP(w, req)
	if w.Code != http.StatusOK {
		t.Fatalf("tables expected 200, got %d", w.Code)
	}
	var tablesResp struct {
		Items []any `json:"items"`
	}
	if err := json.NewDecoder(w.Body).Decode(&tablesResp); err != nil {
		t.Fatalf("decode tables: %v", err)
	}

	req = httptest.NewRequest(http.MethodGet, "/api/public/agent-table", nil)
	w = httptest.NewRecorder()
	router.ServeHTTP(w, req)
	if w.Code != http.StatusBadRequest {
		t.Fatalf("agent-table missing agent_id expected 400, got %d", w.Code)
	}

	req = httptest.NewRequest(http.MethodGet, "/api/public/agent-table?agent_id=agent_missing", nil)
	w = httptest.NewRecorder()
	router.ServeHTTP(w, req)
	if w.Code != http.StatusNotFound {
		t.Fatalf("agent-table missing agent expected 404, got %d", w.Code)
	}

	req = httptest.NewRequest(http.MethodGet, "/api/public/leaderboard", nil)
	w = httptest.NewRecorder()
	router.ServeHTTP(w, req)
	if w.Code != http.StatusOK {
		t.Fatalf("leaderboard expected 200, got %d", w.Code)
	}
	var leaderboardResp struct {
		Items []any `json:"items"`
	}
	if err := json.NewDecoder(w.Body).Decode(&leaderboardResp); err != nil {
		t.Fatalf("decode leaderboard: %v", err)
	}

	req = httptest.NewRequest(http.MethodGet, "/api/public/leaderboard?window=bad", nil)
	w = httptest.NewRecorder()
	router.ServeHTTP(w, req)
	if w.Code != http.StatusBadRequest {
		t.Fatalf("leaderboard invalid window expected 400, got %d", w.Code)
	}

	req = httptest.NewRequest(http.MethodGet, "/api/public/leaderboard?room_id=bad", nil)
	w = httptest.NewRecorder()
	router.ServeHTTP(w, req)
	if w.Code != http.StatusBadRequest {
		t.Fatalf("leaderboard invalid room expected 400, got %d", w.Code)
	}

	req = httptest.NewRequest(http.MethodGet, "/api/public/leaderboard?sort=bad", nil)
	w = httptest.NewRecorder()
	router.ServeHTTP(w, req)
	if w.Code != http.StatusBadRequest {
		t.Fatalf("leaderboard invalid sort expected 400, got %d", w.Code)
	}

	req = httptest.NewRequest(http.MethodGet, "/api/public/tables/history", nil)
	w = httptest.NewRecorder()
	router.ServeHTTP(w, req)
	if w.Code != http.StatusOK {
		t.Fatalf("table history expected 200, got %d", w.Code)
	}
	var historyResp struct {
		Items []struct {
			TableID      string `json:"table_id"`
			RoomName     string `json:"room_name"`
			HandsPlayed  int    `json:"hands_played"`
			Participants []struct {
				AgentID   string `json:"agent_id"`
				AgentName string `json:"agent_name"`
			} `json:"participants"`
		} `json:"items"`
		Total int `json:"total"`
	}
	if err := json.NewDecoder(w.Body).Decode(&historyResp); err != nil {
		t.Fatalf("decode table history: %v", err)
	}

	agentID, _, _ := createTestAgent(t, st, "ProfileAgent")

	req = httptest.NewRequest(http.MethodGet, "/api/public/agents/"+agentID+"/profile", nil)
	w = httptest.NewRecorder()
	router.ServeHTTP(w, req)
	if w.Code != http.StatusOK {
		t.Fatalf("agent profile expected 200, got %d", w.Code)
	}
	var profileResp struct {
		Agent struct {
			AgentID string `json:"agent_id"`
		} `json:"agent"`
	}
	if err := json.NewDecoder(w.Body).Decode(&profileResp); err != nil {
		t.Fatalf("decode agent profile: %v", err)
	}
	if profileResp.Agent.AgentID != agentID {
		t.Fatalf("expected profile agent_id=%s, got %s", agentID, profileResp.Agent.AgentID)
	}

	req = httptest.NewRequest(http.MethodGet, "/api/public/agents/missing-agent/profile", nil)
	w = httptest.NewRecorder()
	router.ServeHTTP(w, req)
	if w.Code != http.StatusNotFound {
		t.Fatalf("agent profile missing agent expected 404, got %d", w.Code)
	}
}
