package agentgateway

import (
	"context"
	"errors"
	"math/rand"
	"strings"
	"sync"
	"time"

	"silicon-casino/internal/game"
	"silicon-casino/internal/ledger"
	"silicon-casino/internal/store"

	"github.com/rs/zerolog/log"
)

const (
	sessionTTL               = 2 * time.Hour
	tableStatusActive        = "active"
	tableStatusClosing       = "closing"
	tableStatusClosed        = "closed"
	defaultReconnectGrace    = 30 * time.Second
	coordinatorSweepInterval = 500 * time.Millisecond
)

var reconnectGracePeriod = defaultReconnectGrace

type sessionState struct {
	session            store.AgentSession
	agent              *store.Agent
	runtime            *tableRuntime
	seat               int
	buffer             *EventBuffer
	disconnected       bool
	disconnectedReason string
}

type Coordinator struct {
	store  *store.Store
	ledger *ledger.Ledger

	mu       sync.Mutex
	waiting  map[string]*sessionState
	sessions map[string]*sessionState
	byAgent  map[string]*sessionState
	tables   map[string]*tableRuntime
}

func NewCoordinator(st *store.Store, led *ledger.Ledger) *Coordinator {
	return &Coordinator{
		store:    st,
		ledger:   led,
		waiting:  map[string]*sessionState{},
		sessions: map[string]*sessionState{},
		byAgent:  map[string]*sessionState{},
		tables:   map[string]*tableRuntime{},
	}
}

func (c *Coordinator) StartJanitor(ctx context.Context, interval time.Duration) {
	if interval <= 0 {
		interval = time.Minute
	}
	expiryTicker := time.NewTicker(interval)
	sweepTicker := time.NewTicker(coordinatorSweepInterval)
	go func() {
		defer expiryTicker.Stop()
		defer sweepTicker.Stop()
		for {
			select {
			case <-ctx.Done():
				return
			case now := <-expiryTicker.C:
				_ = c.expireSessions(ctx, now)
			case now := <-sweepTicker.C:
				c.sweepTableTransitions(ctx, now)
			}
		}
	}()
}

func (c *Coordinator) CreateSession(ctx context.Context, req CreateSessionRequest) (*CreateSessionResponse, error) {
	agent, err := authenticateAgent(ctx, c.store, req.AgentID, req.APIKey)
	if err != nil {
		return nil, err
	}

	c.mu.Lock()
	if old := c.byAgent[agent.ID]; old != nil && old.session.Status != "closed" {
		if c.tryReconnectSessionLocked(ctx, old) {
			res := c.responseForSessionLocked(old)
			c.mu.Unlock()
			return res, nil
		}
		c.mu.Unlock()
		return nil, errors.New("agent_already_in_session")
	}
	c.mu.Unlock()

	room, code := c.selectRoom(ctx, agent.ID, req)
	if room == nil {
		return nil, errors.New(code)
	}

	now := time.Now()
	sess := store.AgentSession{
		ID:        store.NewID(),
		AgentID:   agent.ID,
		RoomID:    room.ID,
		JoinMode:  strings.ToLower(req.JoinMode),
		Status:    "waiting",
		ExpiresAt: now.Add(sessionTTL),
	}

	c.mu.Lock()
	waiter := c.waiting[room.ID]
	if waiter == nil {
		ss := &sessionState{session: sess, agent: agent, buffer: NewEventBuffer(500)}
		c.waiting[room.ID] = ss
		c.sessions[sess.ID] = ss
		c.byAgent[agent.ID] = ss
		ss.buffer.Append("session_joined", sess.ID, map[string]any{
			"table_id": "",
			"room_id":  room.ID,
			"seat_id":  nil,
		})
		c.mu.Unlock()
		if err := c.store.CreateAgentSession(ctx, sess); err != nil {
			return nil, err
		}
		return &CreateSessionResponse{
			SessionID: sess.ID,
			RoomID:    room.ID,
			StreamURL: "/api/agent/sessions/" + sess.ID + "/events",
			ExpiresAt: sess.ExpiresAt,
		}, nil
	}

	delete(c.waiting, room.ID)
	second := &sessionState{session: sess, agent: agent, buffer: NewEventBuffer(500)}
	c.sessions[sess.ID] = second
	c.byAgent[agent.ID] = second
	tableID := store.NewID()
	seat0 := 0
	seat1 := 1
	waiter.session.TableID = tableID
	waiter.session.SeatID = &seat0
	waiter.session.Status = "active"
	waiter.disconnected = false
	waiter.disconnectedReason = ""
	waiter.seat = seat0
	second.session.TableID = tableID
	second.session.SeatID = &seat1
	second.session.Status = "active"
	second.seat = seat1
	c.mu.Unlock()

	if err := c.store.CreateMatchedTableAndSessions(ctx, tableID, room.ID, room.SmallBlindCC, room.BigBlindCC, waiter.session.ID, second.session, seat0, seat1); err != nil {
		log.Error().
			Err(err).
			Str("table_id", tableID).
			Str("room_id", room.ID).
			Str("waiter_session_id", waiter.session.ID).
			Str("second_session_id", second.session.ID).
			Str("waiter_agent_id", waiter.agent.ID).
			Str("second_agent_id", second.agent.ID).
			Msg("create matched table and sessions failed")
		c.mu.Lock()
		delete(c.sessions, second.session.ID)
		delete(c.byAgent, second.agent.ID)
		waiter.session.TableID = ""
		waiter.session.SeatID = nil
		waiter.session.Status = "waiting"
		waiter.seat = 0
		waiter.runtime = nil
		c.waiting[room.ID] = waiter
		c.mu.Unlock()
		return nil, err
	}

	rt, err := c.startTableRuntime(ctx, tableID, room, waiter, second)
	if err != nil {
		log.Error().
			Err(err).
			Str("table_id", tableID).
			Str("room_id", room.ID).
			Str("waiter_session_id", waiter.session.ID).
			Str("second_session_id", second.session.ID).
			Str("waiter_agent_id", waiter.agent.ID).
			Str("second_agent_id", second.agent.ID).
			Msg("start table runtime failed")
		return nil, err
	}
	c.mu.Lock()
	waiter.runtime = rt
	second.runtime = rt
	c.tables[tableID] = rt
	c.emitSessionJoined(waiter)
	c.emitSessionJoined(second)
	c.emitStateSnapshot(waiter)
	c.emitStateSnapshot(second)
	c.emitTurnStarted(rt)
	c.emitPublicSnapshot(rt)
	c.mu.Unlock()

	return &CreateSessionResponse{
		SessionID: second.session.ID,
		TableID:   tableID,
		RoomID:    room.ID,
		SeatID:    second.session.SeatID,
		StreamURL: "/api/agent/sessions/" + second.session.ID + "/events",
		ExpiresAt: second.session.ExpiresAt,
	}, nil
}

func (c *Coordinator) CloseSession(ctx context.Context, sessionID string) error {
	return c.CloseSessionWithReason(ctx, sessionID, "client_closed")
}

func (c *Coordinator) CloseSessionWithReason(ctx context.Context, sessionID, reason string) error {
	c.mu.Lock()
	sess := c.sessions[sessionID]
	if sess == nil {
		c.mu.Unlock()
		return c.store.CloseAgentSession(ctx, sessionID)
	}

	if sess.runtime != nil {
		rt := sess.runtime
		sess.disconnected = true
		sess.disconnectedReason = reason
		c.mu.Unlock()
		c.beginReconnectGrace(ctx, rt, sess.seat, reason)
		return nil
	}

	if sess.buffer != nil {
		sess.buffer.Append("session_closed", sessionID, map[string]any{"reason": reason})
		sess.buffer.Close()
	}
	delete(c.sessions, sessionID)
	if sess.agent != nil {
		delete(c.byAgent, sess.agent.ID)
	}
	if wait := c.waiting[sess.session.RoomID]; wait == sess {
		delete(c.waiting, sess.session.RoomID)
	}
	sess.session.Status = "closed"
	c.mu.Unlock()
	return c.store.CloseAgentSession(ctx, sessionID)
}

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

func (c *Coordinator) FindTableByAgent(agentID string) (string, string, bool) {
	c.mu.Lock()
	defer c.mu.Unlock()
	sess := c.byAgent[agentID]
	if sess == nil || sess.session.Status == "closed" || sess.session.TableID == "" {
		return "", "", false
	}
	return sess.session.TableID, sess.session.RoomID, true
}

func (c *Coordinator) FindOpenSessionByAgent(agentID string) (*CreateSessionResponse, bool) {
	c.mu.Lock()
	defer c.mu.Unlock()
	sess := c.byAgent[agentID]
	if sess == nil || sess.session.Status == "closed" {
		return nil, false
	}
	return c.responseForSessionLocked(sess), true
}

func (c *Coordinator) responseForSessionLocked(sess *sessionState) *CreateSessionResponse {
	if sess == nil {
		return nil
	}
	res := &CreateSessionResponse{
		SessionID: sess.session.ID,
		TableID:   sess.session.TableID,
		RoomID:    sess.session.RoomID,
		SeatID:    sess.session.SeatID,
		StreamURL: "/api/agent/sessions/" + sess.session.ID + "/events",
		ExpiresAt: sess.session.ExpiresAt,
	}
	return res
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

func (c *Coordinator) startTableRuntime(ctx context.Context, tableID string, room *store.Room, p0, p1 *sessionState) (*tableRuntime, error) {
	engine := game.NewEngine(c.store, c.ledger, tableID, room.SmallBlindCC, room.BigBlindCC)
	rt := &tableRuntime{
		id:               tableID,
		room:             room,
		engine:           engine,
		players:          [2]*sessionState{p0, p1},
		turnID:           nextTurnID(),
		publicBuffer:     NewEventBuffer(500),
		status:           tableStatusActive,
		disconnectedSeat: -1,
		turnSeat:         -1,
	}
	players := [2]*game.Player{
		{ID: p0.agent.ID, Name: p0.agent.Name, Seat: 0},
		{ID: p1.agent.ID, Name: p1.agent.Name, Seat: 1},
	}
	if err := rt.engine.StartHand(ctx, players[0], players[1], room.SmallBlindCC, room.BigBlindCC); err != nil {
		return nil, err
	}
	rt.turnID = nextTurnID()
	rt.turnSeat = rt.engine.State.CurrentActor
	rt.turnDeadline = time.Now().Add(rt.engine.State.ActionTimeout)
	c.initReplayRuntime(ctx, rt)
	return rt, nil
}

func (c *Coordinator) selectRoom(ctx context.Context, agentID string, join CreateSessionRequest) (*store.Room, string) {
	balance, err := c.store.GetAccountBalance(ctx, agentID)
	if err != nil {
		return nil, "invalid_action"
	}
	mode := strings.ToLower(join.JoinMode)
	if mode == "" {
		mode = "random"
	}
	if mode == "select" {
		room, err := c.store.GetRoom(ctx, join.RoomID)
		if err != nil || room.Status != "active" {
			return nil, "room_not_found"
		}
		if balance < room.MinBuyinCC {
			return nil, "insufficient_buyin"
		}
		return room, ""
	}
	rooms, err := c.store.ListRooms(ctx)
	if err != nil {
		return nil, "no_available_room"
	}
	eligible := make([]store.Room, 0, len(rooms))
	for _, room := range rooms {
		if balance >= room.MinBuyinCC {
			eligible = append(eligible, room)
		}
	}
	if len(eligible) == 0 {
		return nil, "no_available_room"
	}
	pick := eligible[rand.Intn(len(eligible))]
	return &pick, ""
}

type tableRuntime struct {
	id                  string
	room                *store.Room
	engine              *game.Engine
	players             [2]*sessionState
	turnID              string
	globalSeq           int64
	handSeq             int32
	eventsSinceSnapshot int
	snapshotInterval    int32
	replayClosed        bool
	publicBuffer        *EventBuffer
	status              string
	closeReason         string
	reconnectDeadline   time.Time
	disconnectedSeat    int
	turnDeadline        time.Time
	turnSeat            int
	mu                  sync.Mutex
}

func nextTurnID() string {
	return "turn_" + store.NewID()
}

func (c *Coordinator) emitSessionJoined(sess *sessionState) {
	if sess == nil || sess.buffer == nil {
		return
	}
	sess.buffer.Append("session_joined", sess.session.ID, map[string]any{
		"table_id": sess.session.TableID,
		"room_id":  sess.session.RoomID,
		"seat_id":  sess.seat,
	})
}
