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

func TestSessionsCreateAndDelete(t *testing.T) {
	st, cleanup := testutil.OpenTestStore(t)
	defer cleanup()
	ctx := context.Background()
	led := ledger.New(st)
	coord := NewCoordinator(st, led)

	agentID, err := st.CreateAgent(ctx, "bot-a", "api-key-a", "claim-api-key-a")
	if err != nil {
		t.Fatalf("create agent: %v", err)
	}
	if err := st.EnsureAccount(ctx, agentID, 10000); err != nil {
		t.Fatalf("ensure account: %v", err)
	}
	if err := st.EnsureDefaultRooms(ctx); err != nil {
		t.Fatalf("ensure default rooms: %v", err)
	}

	router := chi.NewRouter()
	router.Post("/api/agent/sessions", SessionsCreateHandler(coord))
	router.Delete("/api/agent/sessions/{session_id}", SessionsDeleteHandler(coord))

	createBody := CreateSessionRequest{
		AgentID:  agentID,
		APIKey:   "api-key-a",
		JoinMode: "random",
	}
	b, _ := json.Marshal(createBody)
	req := httptest.NewRequest(http.MethodPost, "/api/agent/sessions", bytes.NewReader(b))
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)
	if w.Code != http.StatusOK {
		t.Fatalf("create status=%d body=%s", w.Code, w.Body.String())
	}
	var created CreateSessionResponse
	if err := json.Unmarshal(w.Body.Bytes(), &created); err != nil {
		t.Fatalf("decode create response: %v", err)
	}
	if created.SessionID == "" {
		t.Fatal("session_id should not be empty")
	}

	req = httptest.NewRequest(http.MethodDelete, "/api/agent/sessions/"+created.SessionID, nil)
	w = httptest.NewRecorder()
	router.ServeHTTP(w, req)
	if w.Code != http.StatusOK {
		t.Fatalf("delete status=%d body=%s", w.Code, w.Body.String())
	}

	got, err := st.GetAgentSession(ctx, created.SessionID)
	if err != nil {
		t.Fatalf("get session after delete: %v", err)
	}
	if got.Status != "closed" {
		t.Fatalf("expected closed, got %s", got.Status)
	}
}

func TestSessionsCreateRejectInvalidKey(t *testing.T) {
	st, cleanup := testutil.OpenTestStore(t)
	defer cleanup()
	ctx := context.Background()
	coord := NewCoordinator(st, ledger.New(st))

	agentID, err := st.CreateAgent(ctx, "bot-a", "api-key-a", "claim-api-key-a")
	if err != nil {
		t.Fatalf("create agent: %v", err)
	}
	if err := st.EnsureAccount(ctx, agentID, 10000); err != nil {
		t.Fatalf("ensure account: %v", err)
	}
	if err := st.EnsureDefaultRooms(ctx); err != nil {
		t.Fatalf("ensure default rooms: %v", err)
	}

	router := chi.NewRouter()
	router.Post("/api/agent/sessions", SessionsCreateHandler(coord))

	body := CreateSessionRequest{AgentID: agentID, APIKey: "wrong", JoinMode: "random"}
	b, _ := json.Marshal(body)
	req := httptest.NewRequest(http.MethodPost, "/api/agent/sessions", bytes.NewReader(b))
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)
	if w.Code != http.StatusUnauthorized {
		t.Fatalf("expected 401 got %d body=%s", w.Code, w.Body.String())
	}
}

func TestSessionsCreateSelectRoomNotFound(t *testing.T) {
	st, cleanup := testutil.OpenTestStore(t)
	defer cleanup()
	ctx := context.Background()
	coord := NewCoordinator(st, ledger.New(st))

	agentID, err := st.CreateAgent(ctx, "bot-a", "api-key-a", "claim-api-key-a")
	if err != nil {
		t.Fatalf("create agent: %v", err)
	}
	if err := st.EnsureAccount(ctx, agentID, 10000); err != nil {
		t.Fatalf("ensure account: %v", err)
	}

	router := chi.NewRouter()
	router.Post("/api/agent/sessions", SessionsCreateHandler(coord))

	body := CreateSessionRequest{
		AgentID:  agentID,
		APIKey:   "api-key-a",
		JoinMode: "select",
		RoomID:   "missing",
	}
	b, _ := json.Marshal(body)
	req := httptest.NewRequest(http.MethodPost, "/api/agent/sessions", bytes.NewReader(b))
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)
	if w.Code != http.StatusNotFound {
		t.Fatalf("expected 404 got %d body=%s", w.Code, w.Body.String())
	}
}

func TestSessionsDeleteNotFound(t *testing.T) {
	st, cleanup := testutil.OpenTestStore(t)
	defer cleanup()
	coord := NewCoordinator(st, ledger.New(st))
	router := chi.NewRouter()
	router.Delete("/api/agent/sessions/{session_id}", SessionsDeleteHandler(coord))

	req := httptest.NewRequest(http.MethodDelete, "/api/agent/sessions/not-exist", nil)
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)
	if w.Code != http.StatusNotFound {
		t.Fatalf("expected 404 got %d body=%s", w.Code, w.Body.String())
	}
}

func TestSessionsCreateConflictIncludesExistingSession(t *testing.T) {
	st, cleanup := testutil.OpenTestStore(t)
	defer cleanup()
	ctx := context.Background()
	coord := NewCoordinator(st, ledger.New(st))

	agentID, err := st.CreateAgent(ctx, "bot-a", "api-key-a", "claim-api-key-a")
	if err != nil {
		t.Fatalf("create agent: %v", err)
	}
	if err := st.EnsureAccount(ctx, agentID, 10000); err != nil {
		t.Fatalf("ensure account: %v", err)
	}
	if err := st.EnsureDefaultRooms(ctx); err != nil {
		t.Fatalf("ensure default rooms: %v", err)
	}

	router := chi.NewRouter()
	router.Post("/api/agent/sessions", SessionsCreateHandler(coord))

	body := CreateSessionRequest{AgentID: agentID, APIKey: "api-key-a", JoinMode: "random"}
	b, _ := json.Marshal(body)

	firstReq := httptest.NewRequest(http.MethodPost, "/api/agent/sessions", bytes.NewReader(b))
	firstW := httptest.NewRecorder()
	router.ServeHTTP(firstW, firstReq)
	if firstW.Code != http.StatusOK {
		t.Fatalf("expected 200 got %d body=%s", firstW.Code, firstW.Body.String())
	}

	var created CreateSessionResponse
	if err := json.Unmarshal(firstW.Body.Bytes(), &created); err != nil {
		t.Fatalf("decode create response: %v", err)
	}
	if created.SessionID == "" {
		t.Fatal("expected session_id")
	}

	secondReq := httptest.NewRequest(http.MethodPost, "/api/agent/sessions", bytes.NewReader(b))
	secondW := httptest.NewRecorder()
	router.ServeHTTP(secondW, secondReq)
	if secondW.Code != http.StatusConflict {
		t.Fatalf("expected 409 got %d body=%s", secondW.Code, secondW.Body.String())
	}

	var conflict struct {
		Error     string `json:"error"`
		SessionID string `json:"session_id"`
		StreamURL string `json:"stream_url"`
	}
	if err := json.Unmarshal(secondW.Body.Bytes(), &conflict); err != nil {
		t.Fatalf("decode conflict response: %v", err)
	}
	if conflict.Error != "agent_already_in_session" {
		t.Fatalf("expected agent_already_in_session got %s", conflict.Error)
	}
	if conflict.SessionID != created.SessionID {
		t.Fatalf("expected session_id=%s got %s", created.SessionID, conflict.SessionID)
	}
	if conflict.StreamURL == "" {
		t.Fatal("expected stream_url in conflict response")
	}
}
