package main

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"silicon-casino/internal/config"
	"silicon-casino/internal/testutil"
)

func TestAdminEndpointsAuthAndBasicBehavior(t *testing.T) {
	st, cleanup := testutil.OpenTestStore(t)
	defer cleanup()
	cfg := config.ServerConfig{AdminAPIKey: "admin-key"}
	router := newTestRouter(st, cfg)

	unauth := []struct {
		method string
		path   string
		body   string
	}{
		{http.MethodGet, "/api/agents", ""},
		{http.MethodGet, "/api/ledger", ""},
		{http.MethodPost, "/api/topup", `{"agent_id":"x","amount_cc":10}`},
		{http.MethodGet, "/api/rooms", ""},
		{http.MethodPost, "/api/rooms", `{"name":"r","min_buyin_cc":10,"small_blind_cc":1,"big_blind_cc":2}`},
		{http.MethodGet, "/api/debug/vars", ""},
		{http.MethodGet, "/api/providers/rates", ""},
		{http.MethodPost, "/api/providers/rates", `{"provider":"openai","price_per_1k_tokens_usd":0.1,"cc_per_usd":1000,"weight":1}`},
	}
	for _, tc := range unauth {
		req := httptest.NewRequest(tc.method, tc.path, bytes.NewBufferString(tc.body))
		w := httptest.NewRecorder()
		router.ServeHTTP(w, req)
		if w.Code != http.StatusUnauthorized {
			t.Fatalf("unauth %s %s expected 401, got %d", tc.method, tc.path, w.Code)
		}
	}

	adminHeader := http.Header{"X-Admin-Key": []string{"admin-key"}}

	req := httptest.NewRequest(http.MethodGet, "/api/agents", nil)
	req.Header = adminHeader.Clone()
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)
	if w.Code != http.StatusOK {
		t.Fatalf("agents expected 200, got %d", w.Code)
	}

	req = httptest.NewRequest(http.MethodGet, "/api/ledger", nil)
	req.Header = adminHeader.Clone()
	w = httptest.NewRecorder()
	router.ServeHTTP(w, req)
	if w.Code != http.StatusOK {
		t.Fatalf("ledger expected 200, got %d", w.Code)
	}

	agentID, _, _ := createTestAgent(t, st, "AdminTopupAgent")
	topupBody := map[string]any{"agent_id": agentID, "amount_cc": 100}
	topupBytes, _ := json.Marshal(topupBody)
	req = httptest.NewRequest(http.MethodPost, "/api/topup", bytes.NewReader(topupBytes))
	req.Header = adminHeader.Clone()
	w = httptest.NewRecorder()
	router.ServeHTTP(w, req)
	if w.Code != http.StatusOK {
		t.Fatalf("topup expected 200, got %d: %s", w.Code, w.Body.String())
	}

	roomBody := map[string]any{"name": "Test Room", "min_buyin_cc": 10, "small_blind_cc": 1, "big_blind_cc": 2}
	roomBytes, _ := json.Marshal(roomBody)
	req = httptest.NewRequest(http.MethodPost, "/api/rooms", bytes.NewReader(roomBytes))
	req.Header = adminHeader.Clone()
	w = httptest.NewRecorder()
	router.ServeHTTP(w, req)
	if w.Code != http.StatusOK {
		t.Fatalf("rooms POST expected 200, got %d: %s", w.Code, w.Body.String())
	}

	req = httptest.NewRequest(http.MethodGet, "/api/rooms", nil)
	req.Header = adminHeader.Clone()
	w = httptest.NewRecorder()
	router.ServeHTTP(w, req)
	if w.Code != http.StatusOK {
		t.Fatalf("rooms GET expected 200, got %d", w.Code)
	}

	req = httptest.NewRequest(http.MethodGet, "/api/providers/rates", nil)
	req.Header = adminHeader.Clone()
	w = httptest.NewRecorder()
	router.ServeHTTP(w, req)
	if w.Code != http.StatusOK {
		t.Fatalf("providers GET expected 200, got %d", w.Code)
	}

	req = httptest.NewRequest(http.MethodGet, "/api/debug/vars", nil)
	req.Header = adminHeader.Clone()
	w = httptest.NewRecorder()
	router.ServeHTTP(w, req)
	if w.Code != http.StatusOK {
		t.Fatalf("debug vars expected 200, got %d", w.Code)
	}
	if !bytes.Contains(w.Body.Bytes(), []byte("session_create_total")) {
		t.Fatalf("expected debug vars to include metrics")
	}

	rateBody := map[string]any{
		"provider":                "openai",
		"price_per_1k_tokens_usd": 0.1,
		"cc_per_usd":              1000,
		"weight":                  1,
	}
	rateBytes, _ := json.Marshal(rateBody)
	req = httptest.NewRequest(http.MethodPost, "/api/providers/rates", bytes.NewReader(rateBytes))
	req.Header = adminHeader.Clone()
	w = httptest.NewRecorder()
	router.ServeHTTP(w, req)
	if w.Code != http.StatusOK {
		t.Fatalf("providers POST expected 200, got %d: %s", w.Code, w.Body.String())
	}
}
