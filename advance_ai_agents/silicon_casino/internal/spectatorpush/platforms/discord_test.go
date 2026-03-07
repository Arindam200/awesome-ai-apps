package platforms

import (
	"bytes"
	"context"
	"encoding/json"
	"io"
	"net/http"
	"strings"
	"testing"
)

func TestDiscordAdapterPayload(t *testing.T) {
	var got map[string]any
	client := newTestHTTPClient(func(r *http.Request) (*http.Response, error) {
		defer r.Body.Close()
		if err := json.NewDecoder(r.Body).Decode(&got); err != nil {
			t.Fatalf("decode body: %v", err)
		}
		return &http.Response{StatusCode: http.StatusNoContent, Body: io.NopCloser(bytes.NewReader(nil)), Header: make(http.Header)}, nil
	})

	adapter := NewDiscordAdapter(client)
	err := adapter.Send(context.Background(), "https://discord.example/webhook", "", Message{
		Title:       "t",
		Content:     "alert",
		Description: "desc",
		Color:       12345,
		Timestamp:   "2025-01-01T00:00:00Z",
		Footer:      "footer-text",
		Fields: []Field{
			{Name: "street", Value: "flop", Inline: true},
			{Name: "thought", Value: "line", Inline: false},
		},
	})
	if err != nil {
		t.Fatalf("send failed: %v", err)
	}
	if got["content"] != "alert" {
		t.Fatalf("unexpected content: %v", got["content"])
	}
	embeds, ok := got["embeds"].([]any)
	if !ok || len(embeds) != 1 {
		t.Fatalf("unexpected embeds: %#v", got["embeds"])
	}
	embed, ok := embeds[0].(map[string]any)
	if !ok {
		t.Fatalf("unexpected embed type: %#v", embeds[0])
	}
	if embed["description"] != "desc" {
		t.Fatalf("unexpected description: %v", embed["description"])
	}
	if embed["color"] != float64(12345) {
		t.Fatalf("unexpected color: %v", embed["color"])
	}
	if embed["timestamp"] != "2025-01-01T00:00:00Z" {
		t.Fatalf("unexpected timestamp: %v", embed["timestamp"])
	}
	footer, ok := embed["footer"].(map[string]any)
	if !ok || footer["text"] != "footer-text" {
		t.Fatalf("unexpected footer: %#v", embed["footer"])
	}
	fields, ok := embed["fields"].([]any)
	if !ok || len(fields) != 2 {
		t.Fatalf("unexpected fields: %#v", embed["fields"])
	}
	second, ok := fields[1].(map[string]any)
	if !ok || second["inline"] != false {
		t.Fatalf("expected second field inline=false, got %#v", fields[1])
	}
}

func TestDiscordAdapterPanelUpsertUsesPatch(t *testing.T) {
	var methods []string
	var paths []string
	client := newTestHTTPClient(func(r *http.Request) (*http.Response, error) {
		methods = append(methods, r.Method)
		paths = append(paths, r.URL.Path+"?"+r.URL.RawQuery)
		if r.Method == http.MethodPost {
			return &http.Response{
				StatusCode: http.StatusOK,
				Body:       io.NopCloser(strings.NewReader(`{"id":"m123"}`)),
				Header:     make(http.Header),
			}, nil
		}
		return &http.Response{StatusCode: http.StatusNoContent, Body: io.NopCloser(bytes.NewReader(nil)), Header: make(http.Header)}, nil
	})

	endpoint := "https://discord.example/api/webhooks/wid/wtoken"
	adapter := NewDiscordAdapter(client)
	msg := Message{
		PanelKey:    "room|table",
		Title:       "t",
		Content:     "alert",
		Description: "desc",
		Fields:      []Field{{Name: "x", Value: "y", Inline: true}},
	}
	if err := adapter.Send(context.Background(), endpoint, "", msg); err != nil {
		t.Fatalf("first send failed: %v", err)
	}
	if err := adapter.Send(context.Background(), endpoint, "", msg); err != nil {
		t.Fatalf("second send failed: %v", err)
	}

	if len(methods) != 2 {
		t.Fatalf("expected 2 requests, got %d", len(methods))
	}
	if methods[0] != http.MethodPost || methods[1] != http.MethodPatch {
		t.Fatalf("unexpected methods: %#v", methods)
	}
	if !strings.Contains(paths[0], "wait=true") {
		t.Fatalf("expected create request with wait=true, got %s", paths[0])
	}
	if !strings.Contains(paths[1], "/messages/m123") {
		t.Fatalf("expected patch request path with message id, got %s", paths[1])
	}
}

func TestDiscordAdapterForgetPanelForcesRecreate(t *testing.T) {
	var methods []string
	client := newTestHTTPClient(func(r *http.Request) (*http.Response, error) {
		methods = append(methods, r.Method)
		if r.Method == http.MethodPost {
			return &http.Response{
				StatusCode: http.StatusOK,
				Body:       io.NopCloser(strings.NewReader(`{"id":"m123"}`)),
				Header:     make(http.Header),
			}, nil
		}
		return &http.Response{StatusCode: http.StatusNoContent, Body: io.NopCloser(bytes.NewReader(nil)), Header: make(http.Header)}, nil
	})

	endpoint := "https://discord.example/api/webhooks/wid/wtoken"
	adapter := NewDiscordAdapter(client)
	msg := Message{PanelKey: "room|table", Title: "t", Content: "c", Description: "d"}

	if err := adapter.Send(context.Background(), endpoint, "", msg); err != nil {
		t.Fatalf("first send failed: %v", err)
	}
	if err := adapter.Send(context.Background(), endpoint, "", msg); err != nil {
		t.Fatalf("second send failed: %v", err)
	}
	adapter.ForgetPanel(endpoint, msg.PanelKey)
	if err := adapter.Send(context.Background(), endpoint, "", msg); err != nil {
		t.Fatalf("third send failed: %v", err)
	}

	if len(methods) != 3 {
		t.Fatalf("expected 3 requests, got %d", len(methods))
	}
	if methods[0] != http.MethodPost || methods[1] != http.MethodPatch || methods[2] != http.MethodPost {
		t.Fatalf("unexpected method order: %#v", methods)
	}
}
