package spectatorpush

import (
	"context"
	"errors"
	"os"
	"path/filepath"
	"strconv"
	"sync"
	"testing"
	"time"

	"silicon-casino/internal/agentgateway"
	"silicon-casino/internal/spectatorpush/platforms"
)

type fakeAdapter struct {
	mu        sync.Mutex
	calls     int
	failFirst int
	forceFail bool
	messages  []platforms.Message
}

func (f *fakeAdapter) Name() string { return "fake" }

func (f *fakeAdapter) Send(_ context.Context, _ string, _ string, msg platforms.Message) error {
	f.mu.Lock()
	defer f.mu.Unlock()
	f.calls++
	f.messages = append(f.messages, msg)
	if f.forceFail || f.calls <= f.failFirst {
		return errors.New("fail")
	}
	return nil
}

func (f *fakeAdapter) Calls() int {
	f.mu.Lock()
	defer f.mu.Unlock()
	return f.calls
}

func (f *fakeAdapter) Messages() []platforms.Message {
	f.mu.Lock()
	defer f.mu.Unlock()
	out := make([]platforms.Message, len(f.messages))
	copy(out, f.messages)
	return out
}

func (f *fakeAdapter) SetForceFail(v bool) {
	f.mu.Lock()
	defer f.mu.Unlock()
	f.forceFail = v
}

func TestManagerRetryThenSuccess(t *testing.T) {
	cfg := Config{
		Enabled:             true,
		Targets:             []PushTarget{{Platform: "fake", Endpoint: "https://example.com", ScopeType: "all", Enabled: true}},
		Workers:             1,
		RetryMax:            2,
		RetryBase:           5 * time.Millisecond,
		SnapshotMinInterval: time.Second,
	}
	m := NewManager(cfg)
	fake := &fakeAdapter{failFirst: 1}
	m.adapters = map[string]platforms.Adapter{"fake": fake}

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	if err := m.Start(ctx); err != nil {
		t.Fatalf("start manager: %v", err)
	}
	ok := m.enqueue(pushJob{
		Target: cfg.Targets[0],
		Event:  NormalizedEvent{EventType: "action_log", RoomID: "r", TableID: "t"},
		Formatted: FormattedMessage{
			Title:       "title",
			Description: "summary",
		},
	})
	if !ok {
		t.Fatal("expected enqueue success")
	}

	deadline := time.Now().Add(500 * time.Millisecond)
	for time.Now().Before(deadline) {
		if fake.Calls() >= 2 {
			return
		}
		time.Sleep(10 * time.Millisecond)
	}
	t.Fatalf("expected at least 2 calls, got %d", fake.Calls())
}

func TestSnapshotThrottle(t *testing.T) {
	m := NewManager(Config{Enabled: true, SnapshotMinInterval: time.Second})
	ev := NormalizedEvent{TableID: "t1", EventType: "table_snapshot", Street: "flop", TableStatus: "active"}
	if !m.allowSnapshot(ev) {
		t.Fatal("first snapshot should pass")
	}
	if m.allowSnapshot(ev) {
		t.Fatal("second snapshot should be throttled")
	}
	if !m.allowSnapshot(NormalizedEvent{TableID: "t1", EventType: "table_snapshot", Street: "turn", TableStatus: "active"}) {
		t.Fatal("street change should bypass throttling")
	}
}

func TestConfigFileAutoReloadAppliesWithoutRestart(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "targets.json")
	if err := os.WriteFile(path, []byte("[]"), 0o600); err != nil {
		t.Fatalf("write initial targets: %v", err)
	}

	cfg := Config{
		Enabled:             true,
		ConfigPath:          path,
		ConfigReload:        20 * time.Millisecond,
		Targets:             nil,
		Workers:             1,
		RetryMax:            0,
		RetryBase:           5 * time.Millisecond,
		SnapshotMinInterval: time.Second,
	}
	m := NewManager(cfg)
	fake := &fakeAdapter{}
	m.adapters = map[string]platforms.Adapter{"fake": fake}

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	if err := m.Start(ctx); err != nil {
		t.Fatalf("start manager: %v", err)
	}

	meta := agentgateway.TableMeta{TableID: "table_1", RoomID: "room_a"}
	event := agentgateway.StreamEvent{
		EventID:  "1",
		Event:    "action_log",
		ServerTS: time.Now().UnixMilli(),
		Data: map[string]any{
			"table_id":    "table_1",
			"hand_id":     "hand_1",
			"player_seat": 0,
			"action":      "call",
			"amount":      100,
		},
	}

	m.handleEvent(meta, event)
	time.Sleep(40 * time.Millisecond)
	if fake.Calls() != 0 {
		t.Fatalf("expected no calls before config reload, got %d", fake.Calls())
	}

	updated := `[{"platform":"fake","endpoint":"https://example.com","scope_type":"room","scope_value":"room_a","enabled":true}]`
	if err := os.WriteFile(path, []byte(updated), 0o600); err != nil {
		t.Fatalf("write updated targets: %v", err)
	}

	deadline := time.Now().Add(500 * time.Millisecond)
	for time.Now().Before(deadline) {
		if len(m.currentTargets()) == 1 {
			break
		}
		time.Sleep(10 * time.Millisecond)
	}
	if len(m.currentTargets()) != 1 {
		t.Fatal("expected reloaded targets in manager")
	}

	m.handleEvent(meta, event)
	deadline = time.Now().Add(500 * time.Millisecond)
	for time.Now().Before(deadline) {
		if fake.Calls() >= 1 {
			return
		}
		time.Sleep(10 * time.Millisecond)
	}
	t.Fatalf("expected at least 1 call after reload, got %d", fake.Calls())
}

func TestDiscordPanelsCoalesceAndUseFixedPanelKey(t *testing.T) {
	cfg := Config{
		Enabled:             true,
		Targets:             []PushTarget{{Platform: "discord", Endpoint: "https://example.com", ScopeType: "room", ScopeValue: "room_a", Enabled: true}},
		Workers:             1,
		RetryMax:            0,
		RetryBase:           5 * time.Millisecond,
		SnapshotMinInterval: time.Second,
		PanelUpdateInterval: 50 * time.Millisecond,
		PanelRecentActions:  5,
	}
	m := NewManager(cfg)
	fake := &fakeAdapter{}
	m.adapters = map[string]platforms.Adapter{"discord": fake}

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	if err := m.Start(ctx); err != nil {
		t.Fatalf("start manager: %v", err)
	}

	meta := agentgateway.TableMeta{TableID: "table_1", RoomID: "room_a"}
	now := time.Now().UnixMilli()
	for i := 0; i < 3; i++ {
		m.handleEvent(meta, agentgateway.StreamEvent{
			EventID:  "e" + strconv.Itoa(i),
			Event:    "action_log",
			ServerTS: now + int64(i),
			Data: map[string]any{
				"table_id":     "table_1",
				"hand_id":      "hand_1",
				"street":       "flop",
				"table_status": "active",
				"player_seat":  i % 2,
				"action":       "bet",
				"amount":       100 + i,
			},
		})
	}

	time.Sleep(180 * time.Millisecond)
	if fake.Calls() != 1 {
		t.Fatalf("expected coalesced one send, got %d", fake.Calls())
	}
	msgs := fake.Messages()
	if len(msgs) != 1 {
		t.Fatalf("expected one message captured, got %d", len(msgs))
	}
	if msgs[0].PanelKey == "" {
		t.Fatal("expected discord panel message with panel key")
	}
}

func TestDiscordPanelResendAfterDrop(t *testing.T) {
	cfg := Config{
		Enabled:             true,
		Targets:             []PushTarget{{Platform: "discord", Endpoint: "https://example.com", ScopeType: "room", ScopeValue: "room_a", Enabled: true}},
		Workers:             1,
		RetryMax:            0,
		RetryBase:           5 * time.Millisecond,
		SnapshotMinInterval: time.Second,
		PanelUpdateInterval: 30 * time.Millisecond,
		PanelRecentActions:  5,
	}
	m := NewManager(cfg)
	fake := &fakeAdapter{forceFail: true}
	m.adapters = map[string]platforms.Adapter{"discord": fake}

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	if err := m.Start(ctx); err != nil {
		t.Fatalf("start manager: %v", err)
	}

	meta := agentgateway.TableMeta{TableID: "table_drop", RoomID: "room_a"}
	m.handleEvent(meta, agentgateway.StreamEvent{
		EventID:  "e1",
		Event:    "action_log",
		ServerTS: time.Now().UnixMilli(),
		Data: map[string]any{
			"table_id":    "table_drop",
			"hand_id":     "hand_1",
			"player_seat": 0,
			"action":      "bet",
			"amount":      100,
		},
	})

	time.Sleep(120 * time.Millisecond)
	if fake.Calls() == 0 {
		t.Fatal("expected at least one failed send attempt")
	}

	fake.SetForceFail(false)
	time.Sleep(150 * time.Millisecond)
	if fake.Calls() < 2 {
		t.Fatalf("expected resend after recovery, got calls=%d", fake.Calls())
	}
}
