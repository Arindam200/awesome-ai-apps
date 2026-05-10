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

func TestErrorResponsesAreJSON(t *testing.T) {
	st, cleanup := testutil.OpenTestStore(t)
	defer cleanup()
	router := newTestRouter(st, config.ServerConfig{})

	req := httptest.NewRequest(http.MethodPost, "/api/agents/register", bytes.NewBufferString("{"))
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)
	if w.Code != http.StatusBadRequest {
		t.Fatalf("expected 400, got %d", w.Code)
	}
	var errResp map[string]string
	if err := json.NewDecoder(w.Body).Decode(&errResp); err != nil {
		t.Fatalf("decode error response: %v", err)
	}
	if errResp["error"] != "invalid_json" {
		t.Fatalf("expected invalid_json, got %q", errResp["error"])
	}

	req = httptest.NewRequest(http.MethodGet, "/api/public/agent-table", nil)
	w = httptest.NewRecorder()
	router.ServeHTTP(w, req)
	if w.Code != http.StatusBadRequest {
		t.Fatalf("expected 400, got %d", w.Code)
	}
	errResp = map[string]string{}
	if err := json.NewDecoder(w.Body).Decode(&errResp); err != nil {
		t.Fatalf("decode error response: %v", err)
	}
	if errResp["error"] != "invalid_request" {
		t.Fatalf("expected invalid_request, got %q", errResp["error"])
	}
}
