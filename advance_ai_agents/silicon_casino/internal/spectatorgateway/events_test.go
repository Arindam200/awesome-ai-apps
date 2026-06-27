package spectatorgateway

import (
	"bufio"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"github.com/go-chi/chi/v5"
)

func readSpectatorEvent(t *testing.T, rd *bufio.Reader, timeout time.Duration) string {
	t.Helper()
	ch := make(chan string, 1)
	errCh := make(chan error, 1)
	go func() {
		for {
			line, err := rd.ReadString('\n')
			if err != nil {
				errCh <- err
				return
			}
			if strings.HasPrefix(line, "event: ") {
				ch <- strings.TrimSpace(strings.TrimPrefix(line, "event: "))
				return
			}
		}
	}()
	select {
	case ev := <-ch:
		return ev
	case err := <-errCh:
		t.Fatalf("read event: %v", err)
	case <-time.After(timeout):
		t.Fatal("timeout waiting for event")
	}
	return ""
}

func TestSpectatorEventsReceiveSnapshotAndFilter(t *testing.T) {
	prev := pingInterval
	pingInterval = 20 * time.Millisecond
	defer func() { pingInterval = prev }()

	coord, tableID := setupCoordWithTable(t)
	router := chi.NewRouter()
	router.Get("/api/public/spectate/events", EventsHandler(coord))
	server := httptest.NewServer(router)
	defer server.Close()

	resp, err := http.Get(server.URL + "/api/public/spectate/events?table_id=" + tableID)
	if err != nil {
		t.Fatalf("open stream: %v", err)
	}
	defer resp.Body.Close()
	if ct := resp.Header.Get("Content-Type"); ct != "text/event-stream" {
		t.Fatalf("expected Content-Type text/event-stream, got %q", ct)
	}
	cc := resp.Header.Get("Cache-Control")
	if !strings.Contains(cc, "no-cache") || !strings.Contains(cc, "no-transform") {
		t.Fatalf("expected Cache-Control to include no-cache and no-transform, got %q", cc)
	}
	if v := resp.Header.Get("X-Accel-Buffering"); v != "no" {
		t.Fatalf("expected X-Accel-Buffering no, got %q", v)
	}
	rd := bufio.NewReader(resp.Body)
	ev := readSpectatorEvent(t, rd, time.Second)
	if ev == "" {
		t.Fatal("expected first event")
	}

	resp2, err := http.Get(server.URL + "/api/public/spectate/events?table_id=missing")
	if err != nil {
		t.Fatalf("open missing stream: %v", err)
	}
	defer resp2.Body.Close()
	if resp2.StatusCode != http.StatusNotFound {
		t.Fatalf("expected 404 for missing table, got %d", resp2.StatusCode)
	}
}
