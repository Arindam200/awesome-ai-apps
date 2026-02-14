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

type DiscordAdapter struct {
	client    *HTTPClient
	mu        sync.Mutex
	messageBy map[string]string
}

func NewDiscordAdapter(client *HTTPClient) *DiscordAdapter {
	return &DiscordAdapter{
		client:    client,
		messageBy: map[string]string{},
	}
}

func (a *DiscordAdapter) Name() string {
	return "discord"
}

func (a *DiscordAdapter) Send(ctx context.Context, endpoint, _ string, msg Message) error {
	type embedField struct {
		Name   string `json:"name"`
		Value  string `json:"value"`
		Inline bool   `json:"inline"`
	}
	fields := make([]embedField, 0, len(msg.Fields))
	for _, f := range msg.Fields {
		fields = append(fields, embedField{Name: f.Name, Value: f.Value, Inline: f.Inline})
	}
	embed := map[string]any{
		"title":       msg.Title,
		"description": msg.Description,
		"fields":      fields,
		"color":       msg.Color,
	}
	if msg.Timestamp != "" {
		embed["timestamp"] = msg.Timestamp
	}
	if msg.Footer != "" {
		embed["footer"] = map[string]string{"text": msg.Footer}
	}
	payload := map[string]any{
		"content": msg.Content,
		"embeds": []map[string]any{
			embed,
		},
	}
	if strings.TrimSpace(msg.PanelKey) == "" {
		return a.client.PostJSON(ctx, endpoint, nil, payload)
	}

	key := endpoint + "|" + strings.TrimSpace(msg.PanelKey)
	msgID := a.getMessageID(key)
	if msgID == "" {
		createdID, err := a.createPanelMessage(ctx, endpoint, payload)
		if err != nil {
			return err
		}
		a.setMessageID(key, createdID)
		return nil
	}

	editURL, ok := messageEditURL(endpoint, msgID)
	if !ok {
		return a.client.PostJSON(ctx, endpoint, nil, payload)
	}
	status, _, err := a.client.PatchJSONWithResponse(ctx, editURL, nil, payload)
	if err == nil {
		return nil
	}
	if status != http.StatusNotFound {
		return err
	}

	createdID, createErr := a.createPanelMessage(ctx, endpoint, payload)
	if createErr != nil {
		return createErr
	}
	a.setMessageID(key, createdID)
	return nil
}

func (a *DiscordAdapter) getMessageID(key string) string {
	a.mu.Lock()
	defer a.mu.Unlock()
	return a.messageBy[key]
}

func (a *DiscordAdapter) setMessageID(key, msgID string) {
	a.mu.Lock()
	defer a.mu.Unlock()
	a.messageBy[key] = msgID
}

func (a *DiscordAdapter) ForgetPanel(endpoint, panelKey string) {
	key := strings.TrimSpace(endpoint) + "|" + strings.TrimSpace(panelKey)
	if key == "|" {
		return
	}
	a.mu.Lock()
	defer a.mu.Unlock()
	delete(a.messageBy, key)
}

func (a *DiscordAdapter) createPanelMessage(ctx context.Context, endpoint string, payload map[string]any) (string, error) {
	waitEndpoint := endpoint
	if strings.Contains(waitEndpoint, "?") {
		waitEndpoint += "&wait=true"
	} else {
		waitEndpoint += "?wait=true"
	}
	_, body, err := a.client.PostJSONWithResponse(ctx, waitEndpoint, nil, payload)
	if err != nil {
		return "", err
	}
	var raw map[string]any
	if json.Unmarshal(body, &raw) == nil {
		if id, ok := raw["id"].(string); ok && strings.TrimSpace(id) != "" {
			return id, nil
		}
	}
	return "", fmt.Errorf("discord webhook create message missing id")
}

func messageEditURL(endpoint, msgID string) (string, bool) {
	if strings.TrimSpace(endpoint) == "" || strings.TrimSpace(msgID) == "" {
		return "", false
	}
	u, err := url.Parse(endpoint)
	if err != nil {
		return "", false
	}
	parts := strings.Split(strings.Trim(u.Path, "/"), "/")
	if len(parts) < 4 {
		return "", false
	}
	// /api/webhooks/{webhook.id}/{webhook.token}
	if parts[0] != "api" || parts[1] != "webhooks" {
		return "", false
	}
	u.Path = "/api/webhooks/" + parts[2] + "/" + parts[3] + "/messages/" + msgID
	u.RawQuery = ""
	return u.String(), true
}
