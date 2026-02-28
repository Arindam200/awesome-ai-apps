package platforms

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"time"
)

type HTTPClient struct {
	inner *http.Client
}

func NewHTTPClient(timeout time.Duration) *HTTPClient {
	if timeout <= 0 {
		timeout = 5 * time.Second
	}
	return &HTTPClient{inner: &http.Client{Timeout: timeout}}
}

func (c *HTTPClient) PostJSON(ctx context.Context, endpoint string, headers map[string]string, body any) error {
	_, _, err := c.PostJSONWithResponse(ctx, endpoint, headers, body)
	return err
}

func (c *HTTPClient) PostJSONWithResponse(ctx context.Context, endpoint string, headers map[string]string, body any) (int, []byte, error) {
	return c.sendJSON(ctx, http.MethodPost, endpoint, headers, body)
}

func (c *HTTPClient) PatchJSONWithResponse(ctx context.Context, endpoint string, headers map[string]string, body any) (int, []byte, error) {
	return c.sendJSON(ctx, http.MethodPatch, endpoint, headers, body)
}

func (c *HTTPClient) sendJSON(ctx context.Context, method, endpoint string, headers map[string]string, body any) (int, []byte, error) {
	raw, err := json.Marshal(body)
	if err != nil {
		return 0, nil, err
	}
	req, err := http.NewRequestWithContext(ctx, method, endpoint, bytes.NewReader(raw))
	if err != nil {
		return 0, nil, err
	}
	req.Header.Set("Content-Type", "application/json")
	for k, v := range headers {
		req.Header.Set(k, v)
	}

	resp, err := c.inner.Do(req)
	if err != nil {
		return 0, nil, err
	}
	defer resp.Body.Close()
	bodyRaw, readErr := io.ReadAll(resp.Body)
	if readErr != nil {
		return resp.StatusCode, nil, readErr
	}
	if resp.StatusCode >= 200 && resp.StatusCode < 300 {
		return resp.StatusCode, bodyRaw, nil
	}
	return resp.StatusCode, bodyRaw, fmt.Errorf("push failed with status %d", resp.StatusCode)
}
