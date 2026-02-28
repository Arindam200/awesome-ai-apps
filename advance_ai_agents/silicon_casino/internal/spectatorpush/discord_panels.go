package spectatorpush

import (
	"context"
	"fmt"
	"strconv"
	"strings"
	"time"
)

type discordPanelState struct {
	key         string
	target      PushTarget
	tableID     string
	roomID      string
	handID      string
	street      string
	tableState  string
	reason      string
	potCC       int64
	turnSeat    *int
	lastAction  string
	lastThought string
	lastTS      int64
	recent      []string
	dirty       bool
	inflight    bool
	terminal    bool
}

func (m *Manager) accumulateDiscordPanel(target PushTarget, ev NormalizedEvent) {
	if ev.TableID == "" {
		return
	}
	panelKey := targetKey(target) + "|" + ev.TableID

	m.mu.Lock()
	defer m.mu.Unlock()

	panel := m.panelByKey[panelKey]
	if panel == nil {
		panel = &discordPanelState{
			key:      panelKey,
			target:   target,
			tableID:  ev.TableID,
			roomID:   ev.RoomID,
			dirty:    true,
			inflight: false,
			recent:   make([]string, 0, m.cfg.PanelRecentActions),
			terminal: false,
		}
		m.panelByKey[panelKey] = panel
	}
	if panel.terminal {
		return
	}

	panel.target = target
	panel.roomID = fallback(ev.RoomID, panel.roomID)
	panel.handID = fallback(ev.HandID, panel.handID)
	panel.street = fallback(ev.Street, panel.street)
	panel.tableState = fallback(ev.TableStatus, panel.tableState)
	if ev.Pot != nil {
		panel.potCC = *ev.Pot
	}
	if ev.CurrentSeat != nil {
		seat := *ev.CurrentSeat
		panel.turnSeat = &seat
	}
	if ev.CloseReason != "" {
		panel.reason = ev.CloseReason
	}
	if ev.ServerTS > panel.lastTS {
		panel.lastTS = ev.ServerTS
	}
	if ev.EventType == "action_log" {
		actionLine := renderActionLine(ev)
		panel.lastAction = actionLine
		if ev.ThoughtLog != "" {
			panel.lastThought = trimText(strings.TrimSpace(ev.ThoughtLog), 120)
		}
		panel.recent = append(panel.recent, actionLine)
		limit := m.cfg.PanelRecentActions
		if limit <= 0 {
			limit = 5
		}
		if len(panel.recent) > limit {
			panel.recent = panel.recent[len(panel.recent)-limit:]
		}
	}
	if ev.EventType == "table_closed" {
		panel.tableState = "closed"
	}
	panel.dirty = true
}

func (m *Manager) flushDiscordPanelsLoop(ctx context.Context) {
	ticker := time.NewTicker(m.cfg.PanelUpdateInterval)
	defer ticker.Stop()
	for {
		select {
		case <-ctx.Done():
			return
		case <-m.done:
			return
		case <-ticker.C:
			m.flushDirtyDiscordPanels()
		}
	}
}

func (m *Manager) flushDirtyDiscordPanels() {
	m.flushMu.Lock()
	defer m.flushMu.Unlock()

	type flushItem struct {
		key       string
		target    PushTarget
		tableID   string
		formatted FormattedMessage
		terminal  bool
	}
	items := make([]flushItem, 0)

	m.mu.Lock()
	for key, panel := range m.panelByKey {
		if panel == nil || !panel.dirty || panel.terminal || panel.inflight {
			continue
		}
		msg := formatDiscordPanelMessage(panel)
		panel.inflight = true
		items = append(items, flushItem{
			key:       key,
			target:    panel.target,
			tableID:   panel.tableID,
			formatted: msg,
			terminal:  panel.tableState == "closed",
		})
	}
	m.mu.Unlock()

	for _, it := range items {
		job := pushJob{
			Target:        it.target,
			Event:         NormalizedEvent{EventType: "panel_update", TableID: it.tableID},
			Formatted:     it.formatted,
			PanelStateKey: it.key,
			PanelTerminal: it.terminal,
		}
		if !m.enqueue(job) {
			metricPushDroppedTotal.Add(1)
			m.mu.Lock()
			panel := m.panelByKey[it.key]
			if panel != nil {
				panel.inflight = false
			}
			m.mu.Unlock()
			continue
		}
	}
}

func (m *Manager) markPanelDeliverySuccess(job pushJob) {
	if job.PanelStateKey == "" {
		return
	}
	m.mu.Lock()
	defer m.mu.Unlock()
	panel := m.panelByKey[job.PanelStateKey]
	if panel == nil {
		return
	}
	panel.inflight = false
	panel.dirty = false
	if job.PanelTerminal {
		delete(m.panelByKey, job.PanelStateKey)
	}
}

func (m *Manager) markPanelDeliveryDropped(job pushJob) {
	if job.PanelStateKey == "" {
		return
	}
	m.mu.Lock()
	defer m.mu.Unlock()
	panel := m.panelByKey[job.PanelStateKey]
	if panel == nil {
		return
	}
	panel.inflight = false
	panel.dirty = true
}

func formatDiscordPanelMessage(panel *discordPanelState) FormattedMessage {
	if panel == nil {
		return FormattedMessage{}
	}
	room := roomLabel(panel.roomID)
	table := tableLabel(panel.tableID)
	status := fallback(panel.tableState, "active")
	fields := []MessageField{
		{Name: "🃏 Street", Value: titleCase(fallback(panel.street, "-")), Inline: true},
		{Name: "💰 Pot", Value: fmt.Sprintf("%dcc", panel.potCC), Inline: true},
		{Name: "🎯 Turn", Value: seatLabel(panel.turnSeat), Inline: true},
		{Name: "⚡ Last Action", Value: fallback(panel.lastAction, "No action yet"), Inline: true},
		{Name: "🕒 Last Update", Value: updateClock(panel.lastTS), Inline: true},
	}
	if panel.reason != "" {
		fields = append(fields, MessageField{Name: "⚠️ Reason", Value: panel.reason, Inline: false})
	}
	if panel.lastThought != "" {
		fields = append(fields, MessageField{Name: "💭 Thought", Value: panel.lastThought, Inline: false})
	}

	actions := "No actions yet"
	if len(panel.recent) > 0 {
		actions = strings.Join(panel.recent, "\n")
	}
	fields = append(fields, MessageField{Name: "📜 Recent Actions", Value: actions, Inline: false})

	color := colorSnapshot
	if status == "closed" {
		color = colorCritical
	}

	return FormattedMessage{
		PanelKey:    panel.key,
		Title:       fmt.Sprintf("%s | %s | %s", table, room, statusBadge(status)),
		Content:     "",
		Description: fmt.Sprintf("%s | Pot %dcc | %s", titleCase(fallback(panel.street, "-")), panel.potCC, turnSummary(panel.turnSeat)),
		Color:       color,
		Timestamp:   eventTimestamp(panel.lastTS),
		Footer:      fmt.Sprintf("room:%s | table:%s | hand:%s", shortID(fallback(panel.roomID, "-"), 8), shortID(fallback(panel.tableID, "-"), 8), shortID(fallback(panel.handID, "-"), 8)),
		Fields:      fields,
	}
}

func renderActionLine(ev NormalizedEvent) string {
	amount := ""
	if ev.Amount != nil {
		amount = " " + strconv.FormatInt(*ev.Amount, 10) + "cc"
	}
	line := fmt.Sprintf("S%s %s%s", seatText(ev.ActorSeat), fallback(ev.Action, "action"), amount)
	if ev.ThoughtLog != "" {
		line += " - " + trimText(strings.TrimSpace(ev.ThoughtLog), 72)
	}
	return line
}

func roomLabel(roomID string) string {
	id := strings.TrimSpace(roomID)
	if id == "" {
		return "Room"
	}
	return "Room " + shortID(id, 6)
}

func tableLabel(tableID string) string {
	id := strings.TrimSpace(tableID)
	if id == "" {
		return "Table"
	}
	if len(id) <= 4 {
		return "Table #" + id
	}
	return "Table #" + id[len(id)-4:]
}

func seatLabel(seat *int) string {
	if seat == nil {
		return "-"
	}
	return "Seat " + strconv.Itoa(*seat)
}

func turnSummary(seat *int) string {
	if seat == nil {
		return "Awaiting action"
	}
	return "Seat " + strconv.Itoa(*seat) + " to act"
}

func titleCase(v string) string {
	v = strings.TrimSpace(v)
	if v == "" {
		return "-"
	}
	return strings.ToUpper(v[:1]) + v[1:]
}

func statusBadge(status string) string {
	s := strings.ToLower(strings.TrimSpace(status))
	switch s {
	case "active":
		return "🟢 Active"
	case "closing":
		return "🟡 Reconnect"
	case "closed":
		return "🔴 Closed"
	default:
		return "⚪ " + titleCase(status)
	}
}

func updateClock(ms int64) string {
	if ms <= 0 {
		return "-"
	}
	return time.UnixMilli(ms).Format("15:04:05")
}
