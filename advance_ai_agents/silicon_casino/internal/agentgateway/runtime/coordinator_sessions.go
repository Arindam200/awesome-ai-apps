package runtime

import (
	"context"
	"errors"
	"math/rand"
	"strings"
	"time"

	"silicon-casino/internal/game"
	"silicon-casino/internal/store"

	"github.com/rs/zerolog/log"
)

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
	observer := c.tableObserver
	tableMeta := TableMeta{
		TableID: tableID,
		RoomID:  room.ID,
	}
	publicBuffer := rt.publicBuffer
	c.mu.Unlock()
	if observer != nil && publicBuffer != nil {
		observer.OnTableStarted(tableMeta, publicBuffer)
	}

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
