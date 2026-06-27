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

func TestFeishuAdapterPayloadAndHeader(t *testing.T) {
	var got map[string]any
	var headerSig string
	client := newTestHTTPClient(func(r *http.Request) (*http.Response, error) {
		headerSig = r.Header.Get("X-Lark-Signature")
		defer r.Body.Close()
		if err := json.NewDecoder(r.Body).Decode(&got); err != nil {
			t.Fatalf("decode body: %v", err)
		}
		return &http.Response{StatusCode: http.StatusOK, Body: io.NopCloser(bytes.NewReader(nil)), Header: make(http.Header)}, nil
	})

	adapter := NewFeishuAdapter(client)
	err := adapter.Send(context.Background(), "https://feishu.example/hook", "sig-1", Message{
		Title:       "t",
		Description: "summary",
		Fields:      []Field{{Name: "status", Value: "active", Inline: true}},
	})
	if err != nil {
		t.Fatalf("send failed: %v", err)
	}
	if headerSig != "sig-1" {
		t.Fatalf("unexpected signature header: %s", headerSig)
	}
	if got["msg_type"] != "interactive" {
		t.Fatalf("unexpected msg_type: %v", got["msg_type"])
	}
}

func TestFeishuAdapterPanelUpsertUsesPatch(t *testing.T) {
	var methods []string
	var paths []string
	var authHeader string
	client := newTestHTTPClient(func(r *http.Request) (*http.Response, error) {
		methods = append(methods, r.Method)
		paths = append(paths, r.URL.Path)
		if r.Method == http.MethodPatch {
			authHeader = r.Header.Get("Authorization")
		}
		if r.Method == http.MethodPost {
			return &http.Response{
				StatusCode: http.StatusOK,
				Body:       io.NopCloser(strings.NewReader(`{"data":{"message_id":"f001"}}`)),
				Header:     make(http.Header),
			}, nil
		}
		return &http.Response{StatusCode: http.StatusOK, Body: io.NopCloser(bytes.NewReader(nil)), Header: make(http.Header)}, nil
	})

	endpoint := "https://open.feishu.cn/open-apis/bot/v2/hook/abc"
	adapter := NewFeishuAdapter(client)
	msg := Message{
		PanelKey:    "room|table",
		Title:       "t",
		Description: "summary",
		Fields:      []Field{{Name: "status", Value: "active", Inline: true}},
	}
	secret := "sig:sig-1;bearer:token-1"
	if err := adapter.Send(context.Background(), endpoint, secret, msg); err != nil {
		t.Fatalf("first send failed: %v", err)
	}
	if err := adapter.Send(context.Background(), endpoint, secret, msg); err != nil {
		t.Fatalf("second send failed: %v", err)
	}
	adapter.ForgetPanel(endpoint, msg.PanelKey)
	if err := adapter.Send(context.Background(), endpoint, secret, msg); err != nil {
		t.Fatalf("third send failed: %v", err)
	}

	if len(methods) != 3 {
		t.Fatalf("expected 3 requests, got %d", len(methods))
	}
	if methods[0] != http.MethodPost || methods[1] != http.MethodPatch || methods[2] != http.MethodPost {
		t.Fatalf("unexpected method sequence: %#v", methods)
	}
	if !strings.HasSuffix(paths[1], "/open-apis/im/v1/messages/f001") {
		t.Fatalf("unexpected patch path: %s", paths[1])
	}
	if authHeader != "Bearer token-1" {
		t.Fatalf("unexpected auth header: %s", authHeader)
	}
}
