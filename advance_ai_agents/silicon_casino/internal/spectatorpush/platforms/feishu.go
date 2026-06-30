package platforms

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"net/url"
	"strings"
	"sync"
)

type FeishuAdapter struct {
	client    *HTTPClient
	mu        sync.Mutex
	messageBy map[string]string
}

func NewFeishuAdapter(client *HTTPClient) *FeishuAdapter {
	return &FeishuAdapter{
		client:    client,
		messageBy: map[string]string{},
	}
}

func (a *FeishuAdapter) Name() string {
	return "feishu"
}

func (a *FeishuAdapter) Send(ctx context.Context, endpoint, secret string, msg Message) error {
	signature, bearer := parseFeishuSecret(secret)
	cardFields := make([]map[string]string, 0, len(msg.Fields))
	for _, f := range msg.Fields {
		cardFields = append(cardFields, map[string]string{
			"tag":  "markdown",
			"text": "**" + f.Name + "**: " + f.Value,
		})
	}
	payload := map[string]any{
		"msg_type": "interactive",
		"card": map[string]any{
			"header": map[string]any{
				"title": map[string]any{
					"tag":     "plain_text",
					"content": msg.Title,
				},
				"template": "blue",
			},
			"elements": append([]map[string]string{{
				"tag":  "markdown",
				"text": fallback(msg.Description, msg.Content),
			}}, cardFields...),
		},
	}
	headers := map[string]string{}
	if signature != "" {
		headers["X-Lark-Signature"] = signature
	}
	if strings.TrimSpace(msg.PanelKey) == "" {
		return a.client.PostJSON(ctx, endpoint, headers, payload)
	}

	key := endpoint + "|" + strings.TrimSpace(msg.PanelKey)
	msgID := a.getMessageID(key)
	if msgID == "" {
		createdID, err := a.createPanelMessage(ctx, endpoint, headers, payload)
		if err != nil {
			return err
		}
		a.setMessageID(key, createdID)
		return nil
	}

	editURL, ok := feishuEditURL(endpoint, msgID)
	if !ok {
		return a.client.PostJSON(ctx, endpoint, headers, payload)
	}
	patchHeaders := map[string]string{}
	if bearer != "" {
		patchHeaders["Authorization"] = "Bearer " + bearer
	}
	status, _, err := a.client.PatchJSONWithResponse(ctx, editURL, patchHeaders, payload)
	if err == nil {
		return nil
	}
	if status != http.StatusNotFound {
		return err
	}

	createdID, createErr := a.createPanelMessage(ctx, endpoint, headers, payload)
	if createErr != nil {
		return createErr
	}
	a.setMessageID(key, createdID)
	return nil
}

func (a *FeishuAdapter) createPanelMessage(ctx context.Context, endpoint string, headers map[string]string, payload map[string]any) (string, error) {
	_, body, err := a.client.PostJSONWithResponse(ctx, endpoint, headers, payload)
	if err != nil {
		return "", err
	}
	var raw map[string]any
	if err := json.Unmarshal(body, &raw); err != nil {
		return "", err
	}
	if id := firstMessageID(raw); id != "" {
		return id, nil
	}
	return "", fmt.Errorf("feishu create message missing id")
}

func (a *FeishuAdapter) getMessageID(key string) string {
	a.mu.Lock()
	defer a.mu.Unlock()
	return a.messageBy[key]
}

func (a *FeishuAdapter) setMessageID(key, msgID string) {
	a.mu.Lock()
	defer a.mu.Unlock()
	a.messageBy[key] = msgID
}

func (a *FeishuAdapter) ForgetPanel(endpoint, panelKey string) {
	key := strings.TrimSpace(endpoint) + "|" + strings.TrimSpace(panelKey)
	if key == "|" {
		return
	}
	a.mu.Lock()
	defer a.mu.Unlock()
	delete(a.messageBy, key)
}

func parseFeishuSecret(secret string) (signature string, bearer string) {
	s := strings.TrimSpace(secret)
	if s == "" {
		return "", ""
	}
	parts := strings.Split(s, ";")
	for _, p := range parts {
		p = strings.TrimSpace(p)
		switch {
		case strings.HasPrefix(p, "sig:"):
			signature = strings.TrimSpace(strings.TrimPrefix(p, "sig:"))
		case strings.HasPrefix(p, "bearer:"):
			bearer = strings.TrimSpace(strings.TrimPrefix(p, "bearer:"))
		case len(parts) == 1:
			signature = p
		}
	}
	return signature, bearer
}

func feishuEditURL(endpoint, msgID string) (string, bool) {
	if strings.TrimSpace(endpoint) == "" || strings.TrimSpace(msgID) == "" {
		return "", false
	}
	u, err := url.Parse(endpoint)
	if err != nil {
		return "", false
	}
	u.Path = "/open-apis/im/v1/messages/" + msgID
	u.RawQuery = ""
	return u.String(), true
}

func firstMessageID(raw map[string]any) string {
	if raw == nil {
		return ""
	}
	if v, ok := raw["message_id"].(string); ok && strings.TrimSpace(v) != "" {
		return v
	}
	if v, ok := raw["id"].(string); ok && strings.TrimSpace(v) != "" {
		return v
	}
	if data, ok := raw["data"].(map[string]any); ok {
		if v, ok := data["message_id"].(string); ok && strings.TrimSpace(v) != "" {
			return v
		}
		if v, ok := data["id"].(string); ok && strings.TrimSpace(v) != "" {
			return v
		}
	}
	return ""
}

func fallback(v, d string) string {
	if v == "" {
		return d
	}
	return v
}
