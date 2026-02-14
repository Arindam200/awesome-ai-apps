package spectatorpush

import (
	"context"
	"errors"
	"sync"
	"testing"
	"time"

	"silicon-casino/internal/spectatorpush/platforms"
)

type failAdapter struct {
	mu    sync.Mutex
	calls int
	fail  bool
}

func (a *failAdapter) Name() string { return "fail" }

func (a *failAdapter) Send(_ context.Context, _ string, _ string, _ platforms.Message) error {
	a.mu.Lock()
	defer a.mu.Unlock()
	a.calls++
	if a.fail {
		return errors.New("failed")
	}
	return nil
}

func (a *failAdapter) Calls() int {
	a.mu.Lock()
	defer a.mu.Unlock()
	return a.calls
}

type panelCleanerAdapter struct {
	mu          sync.Mutex
	calls       int
	forgetCalls int
	lastPanel   string
}

func (a *panelCleanerAdapter) Name() string { return "cleaner" }

func (a *panelCleanerAdapter) Send(_ context.Context, _ string, _ string, _ platforms.Message) error {
	a.mu.Lock()
	defer a.mu.Unlock()
	a.calls++
	return nil
}

func (a *panelCleanerAdapter) ForgetPanel(_ string, panelKey string) {
	a.mu.Lock()
	defer a.mu.Unlock()
	a.forgetCalls++
	a.lastPanel = panelKey
}

func (a *panelCleanerAdapter) Snapshot() (int, int, string) {
	a.mu.Lock()
	defer a.mu.Unlock()
	return a.calls, a.forgetCalls, a.lastPanel
}

func TestRetryStopsAtMaxAttempts(t *testing.T) {
	cfg := Config{
		Enabled:             true,
		Targets:             []PushTarget{{Platform: "fail", Endpoint: "https://example.com", ScopeType: "all", Enabled: true}},
		Workers:             1,
		RetryMax:            1,
		RetryBase:           5 * time.Millisecond,
		SnapshotMinInterval: time.Second,
	}
	m := NewManager(cfg)
	adapter := &failAdapter{fail: true}
	m.adapters = map[string]platforms.Adapter{"fail": adapter}

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	if err := m.Start(ctx); err != nil {
		t.Fatalf("start manager: %v", err)
	}

	if !m.enqueue(pushJob{Target: cfg.Targets[0], Formatted: FormattedMessage{Title: "x", Description: "y"}}) {
		t.Fatal("enqueue failed")
	}
	time.Sleep(120 * time.Millisecond)
	if got := adapter.Calls(); got != 2 {
		t.Fatalf("expected 2 calls (initial + 1 retry), got %d", got)
	}
}

func TestCircuitOpenSkipsSubsequentSends(t *testing.T) {
	cfg := Config{
		Enabled:             true,
		Targets:             []PushTarget{{Platform: "fail", Endpoint: "https://example.com", ScopeType: "all", Enabled: true}},
		Workers:             1,
		RetryMax:            0,
		RetryBase:           5 * time.Millisecond,
		FailureThreshold:    1,
		CircuitOpenDuration: 500 * time.Millisecond,
		SnapshotMinInterval: time.Second,
	}
	m := NewManager(cfg)
	adapter := &failAdapter{fail: true}
	m.adapters = map[string]platforms.Adapter{"fail": adapter}

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	if err := m.Start(ctx); err != nil {
		t.Fatalf("start manager: %v", err)
	}

	job := pushJob{Target: cfg.Targets[0], Formatted: FormattedMessage{Title: "x", Description: "y"}}
	if !m.enqueue(job) {
		t.Fatal("enqueue first failed")
	}
	time.Sleep(40 * time.Millisecond)
	if !m.enqueue(job) {
		t.Fatal("enqueue second failed")
	}
	time.Sleep(80 * time.Millisecond)

	if got := adapter.Calls(); got != 1 {
		t.Fatalf("expected 1 call due to circuit open, got %d", got)
	}
}

func TestTerminalPanelTriggersAdapterCleanup(t *testing.T) {
	cfg := Config{
		Enabled:             true,
		Targets:             []PushTarget{{Platform: "cleaner", Endpoint: "https://example.com", ScopeType: "all", Enabled: true}},
		Workers:             1,
		RetryMax:            0,
		RetryBase:           5 * time.Millisecond,
		SnapshotMinInterval: time.Second,
	}
	m := NewManager(cfg)
	adapter := &panelCleanerAdapter{}
	m.adapters = map[string]platforms.Adapter{"cleaner": adapter}

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	if err := m.Start(ctx); err != nil {
		t.Fatalf("start manager: %v", err)
	}

	if !m.enqueue(pushJob{
		Target:        cfg.Targets[0],
		PanelTerminal: true,
		Formatted: FormattedMessage{
			PanelKey:    "target|table_1",
			Title:       "x",
			Description: "y",
		},
	}) {
		t.Fatal("enqueue failed")
	}
	time.Sleep(80 * time.Millisecond)
	calls, forgetCalls, panel := adapter.Snapshot()
	if calls != 1 {
		t.Fatalf("expected one send call, got %d", calls)
	}
	if forgetCalls != 1 || panel != "target|table_1" {
		t.Fatalf("expected forget call for panel target|table_1, got calls=%d panel=%s", forgetCalls, panel)
	}
}
