package runtime

import (
	"context"
	"time"
)

func (c *Coordinator) beginReconnectGrace(ctx context.Context, rt *tableRuntime, forfeiterSeat int, reason string) {
	if rt == nil {
		return
	}
	var disconnectedAgentID string
	now := time.Now()
	graceDeadline := now.Add(reconnectGracePeriod)

	rt.mu.Lock()
	if rt.status == tableStatusClosed {
		rt.mu.Unlock()
		return
	}
	if rt.status == tableStatusClosing {
		rt.mu.Unlock()
		return
	}
	if forfeiterSeat < 0 || forfeiterSeat > 1 {
		forfeiterSeat = rt.engine.State.CurrentActor
	}
	rt.status = tableStatusClosing
	rt.closeReason = reason
	rt.disconnectedSeat = forfeiterSeat
	rt.reconnectDeadline = graceDeadline
	rt.turnDeadline = time.Time{}
	rt.turnSeat = -1
	if p := rt.players[forfeiterSeat]; p != nil {
		disconnectedAgentID = p.agent.ID
	}
	c.appendReplayEvent(ctx, rt, "reconnect_grace_started", "", map[string]any{
		"table_id":              rt.id,
		"disconnected_agent_id": disconnectedAgentID,
		"grace_ms":              reconnectGracePeriod.Milliseconds(),
		"deadline_ts":           graceDeadline.UnixMilli(),
		"reason":                reason,
	})
	for _, p := range rt.players {
		if p == nil || p.buffer == nil {
			continue
		}
		p.buffer.Append("reconnect_grace_started", p.session.ID, map[string]any{
			"table_id":              rt.id,
			"disconnected_agent_id": disconnectedAgentID,
			"grace_ms":              reconnectGracePeriod.Milliseconds(),
			"deadline_ts":           graceDeadline.UnixMilli(),
		})
	}
	if rt.publicBuffer != nil {
		rt.publicBuffer.Append("reconnect_grace_started", rt.id, map[string]any{
			"table_id":              rt.id,
			"disconnected_agent_id": disconnectedAgentID,
			"grace_ms":              reconnectGracePeriod.Milliseconds(),
			"deadline_ts":           graceDeadline.UnixMilli(),
			"reason":                reason,
		})
	}
	rt.mu.Unlock()

	_ = c.store.MarkTableStatusByID(ctx, rt.id, tableStatusClosing)
	for _, p := range rt.players {
		c.emitStateSnapshot(p)
	}
	c.emitPublicSnapshot(rt)
}

func (c *Coordinator) closeTableWithForfeit(ctx context.Context, rt *tableRuntime, forfeiterSeat int, reason string) {
	if rt == nil {
		return
	}

	var sessionsToClose []string
	var tableID string
	var winnerID string
	var pot int64

	rt.mu.Lock()
	if rt.status == tableStatusClosed {
		rt.mu.Unlock()
		return
	}
	if forfeiterSeat < 0 || forfeiterSeat > 1 {
		if rt.disconnectedSeat >= 0 && rt.disconnectedSeat <= 1 {
			forfeiterSeat = rt.disconnectedSeat
		} else {
			forfeiterSeat = rt.engine.State.CurrentActor
		}
	}
	winnerSeat := 1 - forfeiterSeat
	forfeiter := rt.players[forfeiterSeat]
	winner := rt.players[winnerSeat]
	if rt.engine.State.Players[forfeiterSeat] != nil {
		rt.engine.State.Players[forfeiterSeat].Folded = true
	}
	winnerID, _ = rt.engine.Settle(ctx)
	if winnerID == "" && winner != nil {
		winnerID = winner.agent.ID
	}
	pot = rt.engine.State.Pot
	tableID = rt.id

	forfeiterAgentID := ""
	if forfeiter != nil {
		forfeiterAgentID = forfeiter.agent.ID
	}
	c.appendReplayEvent(ctx, rt, "opponent_forfeited", winnerID, map[string]any{
		"table_id":           rt.id,
		"forfeiter_agent_id": forfeiterAgentID,
		"winner_agent_id":    winnerID,
		"reason":             reason,
	})
	c.appendReplayEvent(ctx, rt, "hand_settled", winnerID, map[string]any{
		"hand_id": rt.engine.State.HandID,
		"winner":  winnerID,
		"pot_cc":  pot,
		"street":  string(rt.engine.State.Street),
	})
	c.appendReplayEvent(ctx, rt, "table_closed", "", map[string]any{"reason": reason})

	rt.status = tableStatusClosed
	rt.closeReason = reason
	rt.reconnectDeadline = time.Time{}
	rt.disconnectedSeat = -1
	rt.turnDeadline = time.Time{}
	rt.turnSeat = -1
	rt.replayClosed = true

	for _, p := range rt.players {
		if p == nil {
			continue
		}
		p.session.Status = "closed"
		p.disconnected = false
		p.disconnectedReason = ""
		sessionsToClose = append(sessionsToClose, p.session.ID)
		if p.buffer != nil {
			p.buffer.Append("opponent_forfeited", p.session.ID, map[string]any{
				"table_id":           rt.id,
				"forfeiter_agent_id": forfeiterAgentID,
				"winner_agent_id":    winnerID,
				"reason":             reason,
			})
			p.buffer.Append("table_closed", p.session.ID, map[string]any{"table_id": rt.id, "reason": reason})
			p.buffer.Append("session_closed", p.session.ID, map[string]any{"reason": reason})
			p.buffer.Close()
		}
	}
	if rt.publicBuffer != nil {
		rt.publicBuffer.Append("opponent_forfeited", rt.id, map[string]any{
			"table_id":           rt.id,
			"forfeiter_agent_id": forfeiterAgentID,
			"winner_agent_id":    winnerID,
			"reason":             reason,
		})
		rt.publicBuffer.Append("table_closed", rt.id, map[string]any{"table_id": rt.id, "reason": reason})
		rt.publicBuffer.Close()
	}
	rt.mu.Unlock()

	_ = c.store.EndHandWithSummary(ctx, rt.engine.State.HandID, winnerID, &pot, string(rt.engine.State.Street))
	_ = c.store.MarkTableStatusByID(ctx, tableID, tableStatusClosed)
	_ = c.store.CloseAgentSessionsByTableID(ctx, tableID)

	c.mu.Lock()
	observer := c.tableObserver
	delete(c.tables, tableID)
	for _, p := range rt.players {
		if p == nil {
			continue
		}
		delete(c.sessions, p.session.ID)
		if p.agent != nil {
			delete(c.byAgent, p.agent.ID)
		}
	}
	c.mu.Unlock()
	if observer != nil {
		observer.OnTableClosed(tableID)
	}

	for _, sessionID := range sessionsToClose {
		_ = c.store.CloseAgentSession(ctx, sessionID)
	}
}

func (c *Coordinator) sweepTableTransitions(ctx context.Context, now time.Time) {
	c.mu.Lock()
	tables := make([]*tableRuntime, 0, len(c.tables))
	for _, rt := range c.tables {
		tables = append(tables, rt)
	}
	c.mu.Unlock()

	for _, rt := range tables {
		rt.mu.Lock()
		status := rt.status
		turnExpired := status == tableStatusActive && !rt.turnDeadline.IsZero() && now.After(rt.turnDeadline)
		graceExpired := status == tableStatusClosing && !rt.reconnectDeadline.IsZero() && now.After(rt.reconnectDeadline)
		turnSeat := rt.turnSeat
		disconnectedSeat := rt.disconnectedSeat
		rt.mu.Unlock()

		if turnExpired {
			c.beginReconnectGrace(ctx, rt, turnSeat, "opponent_action_timeout")
			continue
		}
		if graceExpired {
			c.closeTableWithForfeit(ctx, rt, disconnectedSeat, "opponent_reconnect_timeout")
		}
	}
}

func (c *Coordinator) expireSessions(ctx context.Context, now time.Time) int {
	expired := make([]string, 0)
	c.mu.Lock()
	for id, sess := range c.sessions {
		if sess.session.Status == "closed" {
			continue
		}
		if !sess.session.ExpiresAt.IsZero() && sess.session.ExpiresAt.Before(now) {
			expired = append(expired, id)
		}
	}
	c.mu.Unlock()

	for _, id := range expired {
		_ = c.CloseSessionWithReason(ctx, id, "expired")
	}
	return len(expired)
}
func (c *Coordinator) tryReconnectSessionLocked(ctx context.Context, sess *sessionState) bool {
	if sess == nil || sess.runtime == nil || !sess.disconnected {
		return false
	}
	rt := sess.runtime
	now := time.Now()
	rt.mu.Lock()
	defer rt.mu.Unlock()
	if rt.status != tableStatusClosing {
		return false
	}
	if rt.disconnectedSeat != sess.seat {
		return false
	}
	if !rt.reconnectDeadline.IsZero() && now.After(rt.reconnectDeadline) {
		return false
	}
	sess.disconnected = false
	sess.disconnectedReason = ""
	sess.session.ExpiresAt = now.Add(sessionTTL)
	rt.status = tableStatusActive
	rt.closeReason = ""
	rt.reconnectDeadline = time.Time{}
	rt.disconnectedSeat = -1
	rt.turnSeat = rt.engine.State.CurrentActor
	rt.turnDeadline = now.Add(rt.engine.State.ActionTimeout)
	c.appendReplayEvent(ctx, rt, "opponent_reconnected", sess.agent.ID, map[string]any{
		"table_id": rt.id,
		"agent_id": sess.agent.ID,
	})
	for _, p := range rt.players {
		if p == nil || p.buffer == nil {
			continue
		}
		p.buffer.Append("opponent_reconnected", p.session.ID, map[string]any{
			"table_id": rt.id,
			"agent_id": sess.agent.ID,
		})
	}
	if rt.publicBuffer != nil {
		rt.publicBuffer.Append("opponent_reconnected", rt.id, map[string]any{
			"table_id": rt.id,
			"agent_id": sess.agent.ID,
		})
	}
	for _, p := range rt.players {
		c.emitStateSnapshot(p)
	}
	c.emitTurnStarted(rt)
	c.emitPublicSnapshot(rt)
	_ = c.store.MarkTableStatusByID(ctx, rt.id, tableStatusActive)
	return true
}
