package spectatorpush

import (
	"context"
	"encoding/json"
	"os"
	"strings"
	"sync"
	"time"

	"silicon-casino/internal/agentgateway"
	"silicon-casino/internal/spectatorpush/platforms"
)

type tableSubscription struct {
	meta   agentgateway.TableMeta
	buf    *agentgateway.EventBuffer
	ch     chan agentgateway.StreamEvent
	cancel context.CancelFunc
}

type snapshotState struct {
	lastSentAt time.Time
	street     string
	status     string
}

type breakerState struct {
	consecutiveFailures int
	openUntil           time.Time
}

type Manager struct {
	cfg      Config
	router   Router
	adapters map[string]platforms.Adapter

	dispatchCh chan pushJob
	retryQ     *retryQueue
	done       chan struct{}

	flushMu       sync.Mutex
	mu            sync.Mutex
	started       bool
	subscriptions map[string]*tableSubscription
	snapshotByTbl map[string]snapshotState
	panelByKey    map[string]*discordPanelState
	breakerByKey  map[string]breakerState
}

func NewManager(cfg Config) *Manager {
	client := platforms.NewHTTPClient(cfg.RequestTimeout)
	adapters := map[string]platforms.Adapter{
		"discord": platforms.NewDiscordAdapter(client),
		"feishu":  platforms.NewFeishuAdapter(client),
	}
	if cfg.DispatchBuffer <= 0 {
		cfg.DispatchBuffer = 2048
	}
	if cfg.Workers <= 0 {
		cfg.Workers = 4
	}
	if cfg.RetryBase <= 0 {
		cfg.RetryBase = 500 * time.Millisecond
	}
	if cfg.SnapshotMinInterval <= 0 {
		cfg.SnapshotMinInterval = 3 * time.Second
	}
	if cfg.PanelUpdateInterval <= 0 {
		cfg.PanelUpdateInterval = time.Second
	}
	if cfg.PanelRecentActions <= 0 {
		cfg.PanelRecentActions = 5
	}
	if cfg.FailureThreshold <= 0 {
		cfg.FailureThreshold = 3
	}
	if cfg.CircuitOpenDuration <= 0 {
		cfg.CircuitOpenDuration = 30 * time.Second
	}

	m := &Manager{
		cfg:           cfg,
		router:        Router{},
		adapters:      adapters,
		dispatchCh:    make(chan pushJob, cfg.DispatchBuffer),
		done:          make(chan struct{}),
		subscriptions: map[string]*tableSubscription{},
		snapshotByTbl: map[string]snapshotState{},
		panelByKey:    map[string]*discordPanelState{},
		breakerByKey:  map[string]breakerState{},
	}
	m.retryQ = newRetryQueue(m.dispatchCh, m.done)
	return m
}

func (m *Manager) Start(ctx context.Context) error {
	if !m.cfg.Enabled {
		return nil
	}

	m.mu.Lock()
	if m.started {
		m.mu.Unlock()
		return nil
	}
	m.started = true
	m.mu.Unlock()

	for i := 0; i < m.cfg.Workers; i++ {
		go m.worker(ctx)
	}
	if m.cfg.ConfigPath != "" {
		go m.watchConfigLoop(ctx)
	}
	go m.flushDiscordPanelsLoop(ctx)
	go func() {
		<-ctx.Done()
		close(m.done)
		m.stopAllSubscriptions()
	}()
	return nil
}

func (m *Manager) OnTableStarted(meta agentgateway.TableMeta, buf *agentgateway.EventBuffer) {
	if !m.cfg.Enabled || buf == nil || meta.TableID == "" {
		return
	}

	m.mu.Lock()
	if _, ok := m.subscriptions[meta.TableID]; ok {
		m.mu.Unlock()
		return
	}

	ctx, cancel := context.WithCancel(context.Background())
	sub := &tableSubscription{
		meta:   meta,
		buf:    buf,
		ch:     buf.Subscribe(),
		cancel: cancel,
	}
	m.subscriptions[meta.TableID] = sub
	m.mu.Unlock()

	go m.consumeTable(ctx, sub)
}

func (m *Manager) OnTableClosed(tableID string) {
	if tableID == "" {
		return
	}

	m.mu.Lock()
	sub := m.subscriptions[tableID]
	delete(m.subscriptions, tableID)
	delete(m.snapshotByTbl, tableID)
	m.mu.Unlock()

	if sub == nil {
		return
	}
	sub.cancel()
	sub.buf.Unsubscribe(sub.ch)
}

func (m *Manager) stopAllSubscriptions() {
	m.mu.Lock()
	subs := make([]*tableSubscription, 0, len(m.subscriptions))
	for _, sub := range m.subscriptions {
		subs = append(subs, sub)
	}
	m.subscriptions = map[string]*tableSubscription{}
	m.snapshotByTbl = map[string]snapshotState{}
	m.panelByKey = map[string]*discordPanelState{}
	m.mu.Unlock()

	for _, sub := range subs {
		sub.cancel()
		sub.buf.Unsubscribe(sub.ch)
	}
}

func (m *Manager) consumeTable(ctx context.Context, sub *tableSubscription) {
	for {
		select {
		case <-ctx.Done():
			return
		case <-m.done:
			return
		case ev, ok := <-sub.ch:
			if !ok {
				return
			}
			m.handleEvent(sub.meta, ev)
		}
	}
}

func (m *Manager) handleEvent(meta agentgateway.TableMeta, ev agentgateway.StreamEvent) {
	if ev.Event == "" || ev.Event == "ping" {
		return
	}
	norm := normalizeEvent(meta, ev)
	if norm.EventType == "" {
		return
	}
	if norm.EventType == "table_snapshot" && !m.allowSnapshot(norm) {
		return
	}

	targets := m.router.MatchTargets(m.currentTargets(), norm)
	if len(targets) == 0 {
		return
	}

	for _, target := range targets {
		if strings.EqualFold(target.Platform, "discord") || strings.EqualFold(target.Platform, "feishu") {
			m.accumulateDiscordPanel(target, norm)
			if norm.EventType == "table_closed" {
				m.flushDirtyDiscordPanels()
			}
			continue
		}
		formatted, ok := FormatMessage(norm)
		if !ok {
			continue
		}
		job := pushJob{Target: target, Event: norm, Formatted: formatted}
		if !m.enqueue(job) {
			metricPushDroppedTotal.Add(1)
		}
	}
}

func (m *Manager) allowSnapshot(ev NormalizedEvent) bool {
	now := time.Now()
	m.mu.Lock()
	defer m.mu.Unlock()
	prev := m.snapshotByTbl[ev.TableID]
	if !prev.lastSentAt.IsZero() {
		if now.Sub(prev.lastSentAt) < m.cfg.SnapshotMinInterval && prev.street == ev.Street && prev.status == ev.TableStatus {
			return false
		}
	}
	m.snapshotByTbl[ev.TableID] = snapshotState{lastSentAt: now, street: ev.Street, status: ev.TableStatus}
	return true
}

func (m *Manager) enqueue(job pushJob) bool {
	select {
	case <-m.done:
		return false
	case m.dispatchCh <- job:
		metricPushQueuedTotal.Add(1)
		metricPushQueueLen.Set(int64(len(m.dispatchCh)))
		return true
	default:
		return false
	}
}

func normalizeEvent(meta agentgateway.TableMeta, ev agentgateway.StreamEvent) NormalizedEvent {
	raw := asMap(ev.Data)
	tableID := stringField(raw, "table_id")
	if tableID == "" {
		tableID = meta.TableID
	}
	if tableID == "" {
		tableID = ev.SessionID
	}
	amount := int64Ptr(raw, "amount")
	if amount == nil {
		amount = int64Ptr(raw, "amount_cc")
	}
	pot := int64Ptr(raw, "pot")
	if pot == nil {
		pot = int64Ptr(raw, "pot_cc")
	}
	currentSeat := intPtr(raw, "current_actor_seat")
	seat := intPtr(raw, "player_seat")
	if seat == nil {
		seat = currentSeat
	}
	if seat == nil {
		seat = intPtr(raw, "seat_id")
	}
	closeReason := stringField(raw, "close_reason")
	if closeReason == "" {
		closeReason = stringField(raw, "reason")
	}

	return NormalizedEvent{
		EventID:     ev.EventID,
		EventType:   ev.Event,
		ServerTS:    ev.ServerTS,
		TableID:     tableID,
		RoomID:      meta.RoomID,
		HandID:      stringField(raw, "hand_id"),
		Street:      stringField(raw, "street"),
		ActorSeat:   seat,
		CurrentSeat: currentSeat,
		Action:      stringField(raw, "action"),
		Amount:      amount,
		Pot:         pot,
		ThoughtLog:  stringField(raw, "thought_log"),
		TableStatus: stringField(raw, "table_status"),
		CloseReason: closeReason,
		Raw:         raw,
	}
}

func (m *Manager) currentTargets() []PushTarget {
	m.mu.Lock()
	defer m.mu.Unlock()
	out := make([]PushTarget, len(m.cfg.Targets))
	copy(out, m.cfg.Targets)
	return out
}

func (m *Manager) watchConfigLoop(ctx context.Context) {
	interval := m.cfg.ConfigReload
	if interval <= 0 {
		interval = time.Second
	}
	lastRaw := ""
	if raw, err := os.ReadFile(m.cfg.ConfigPath); err == nil {
		lastRaw = strings.TrimSpace(string(raw))
	}
	ticker := time.NewTicker(interval)
	defer ticker.Stop()
	for {
		select {
		case <-ctx.Done():
			return
		case <-m.done:
			return
		case <-ticker.C:
			raw, err := os.ReadFile(m.cfg.ConfigPath)
			if err != nil {
				metricPushConfigReloadError.Add(1)
				continue
			}
			nextRaw := strings.TrimSpace(string(raw))
			if nextRaw == lastRaw {
				continue
			}
			targets, err := parseTargetsJSON(nextRaw)
			if err != nil {
				metricPushConfigReloadError.Add(1)
				continue
			}
			m.mu.Lock()
			m.cfg.Targets = targets
			m.mu.Unlock()
			lastRaw = nextRaw
			metricPushConfigReloadTotal.Add(1)
		}
	}
}

func asMap(v any) map[string]any {
	if v == nil {
		return map[string]any{}
	}
	if m, ok := v.(map[string]any); ok {
		return m
	}
	raw, err := json.Marshal(v)
	if err != nil {
		return map[string]any{}
	}
	out := map[string]any{}
	if err := json.Unmarshal(raw, &out); err != nil {
		return map[string]any{}
	}
	return out
}

func stringField(m map[string]any, key string) string {
	v, ok := m[key]
	if !ok || v == nil {
		return ""
	}
	s, ok := v.(string)
	if ok {
		return s
	}
	return ""
}

func intPtr(m map[string]any, key string) *int {
	v, ok := m[key]
	if !ok || v == nil {
		return nil
	}
	switch vv := v.(type) {
	case float64:
		x := int(vv)
		return &x
	case int:
		x := vv
		return &x
	case int64:
		x := int(vv)
		return &x
	}
	return nil
}

func int64Ptr(m map[string]any, key string) *int64 {
	v, ok := m[key]
	if !ok || v == nil {
		return nil
	}
	switch vv := v.(type) {
	case float64:
		x := int64(vv)
		return &x
	case int64:
		x := vv
		return &x
	case int:
		x := int64(vv)
		return &x
	}
	return nil
}
