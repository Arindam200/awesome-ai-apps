package store

import (
	"context"

	"silicon-casino/internal/store/sqlcgen"

	"github.com/jackc/pgx/v5"
)

func (s *Store) CreateAgentSession(ctx context.Context, sess AgentSession) error {
	return s.q.CreateAgentSession(ctx, sqlcgen.CreateAgentSessionParams{
		ID:        sess.ID,
		AgentID:   sess.AgentID,
		RoomID:    sess.RoomID,
		TableID:   sess.TableID,
		SeatID:    int4PtrParam(sess.SeatID),
		JoinMode:  sess.JoinMode,
		Status:    sess.Status,
		ExpiresAt: timeParam(&sess.ExpiresAt),
	})
}

func (s *Store) CreateMatchedTableAndSessions(ctx context.Context, tableID, roomID string, sb, bb int64, waiterSessionID string, second AgentSession, seat0, seat1 int) error {
	tx, err := s.Pool.BeginTx(ctx, pgx.TxOptions{})
	if err != nil {
		return err
	}
	defer tx.Rollback(ctx)

	qtx := s.q.WithTx(tx)
	if err := qtx.CreateTable(ctx, sqlcgen.CreateTableParams{
		ID:           tableID,
		RoomID:       textParam(roomID),
		Status:       "active",
		SmallBlindCc: sb,
		BigBlindCc:   bb,
	}); err != nil {
		return err
	}
	if err := qtx.CreateAgentSession(ctx, sqlcgen.CreateAgentSessionParams{
		ID:        second.ID,
		AgentID:   second.AgentID,
		RoomID:    second.RoomID,
		TableID:   second.TableID,
		SeatID:    int4Param(int32(seat1)),
		JoinMode:  second.JoinMode,
		Status:    second.Status,
		ExpiresAt: timestamptzParam(second.ExpiresAt),
	}); err != nil {
		return err
	}
	if rows, err := qtx.UpdateAgentSessionMatch(ctx, sqlcgen.UpdateAgentSessionMatchParams{
		ID:      waiterSessionID,
		TableID: textParam(tableID),
		SeatID:  int4Param(int32(seat0)),
	}); err != nil {
		return err
	} else if rows == 0 {
		return ErrNotFound
	}
	if rows, err := qtx.UpdateAgentSessionMatch(ctx, sqlcgen.UpdateAgentSessionMatchParams{
		ID:      second.ID,
		TableID: textParam(tableID),
		SeatID:  int4Param(int32(seat1)),
	}); err != nil {
		return err
	} else if rows == 0 {
		return ErrNotFound
	}
	return tx.Commit(ctx)
}

func (s *Store) GetAgentSession(ctx context.Context, sessionID string) (*AgentSession, error) {
	r, err := s.q.GetAgentSessionByID(ctx, sessionID)
	if err != nil {
		return nil, mapNotFound(err)
	}
	return &AgentSession{
		ID:        r.ID,
		AgentID:   r.AgentID,
		RoomID:    r.RoomID,
		TableID:   textVal(r.TableID),
		SeatID:    intPtrVal(r.SeatID),
		JoinMode:  r.JoinMode,
		Status:    r.Status,
		ExpiresAt: r.ExpiresAt.Time,
		CreatedAt: r.CreatedAt.Time,
		ClosedAt:  timePtrVal(r.ClosedAt),
	}, nil
}

func (s *Store) UpdateAgentSessionMatch(ctx context.Context, sessionID, tableID string, seatID int) error {
	rows, err := s.q.UpdateAgentSessionMatch(ctx, sqlcgen.UpdateAgentSessionMatchParams{
		ID:      sessionID,
		TableID: textParam(tableID),
		SeatID:  int4Param(int32(seatID)),
	})
	if err != nil {
		return err
	}
	if rows == 0 {
		return ErrNotFound
	}
	return nil
}

func (s *Store) CloseAgentSession(ctx context.Context, sessionID string) error {
	rows, err := s.q.CloseAgentSession(ctx, sessionID)
	if err != nil {
		return err
	}
	if rows == 0 {
		return ErrNotFound
	}
	return nil
}

func (s *Store) CloseAgentSessionsByTableID(ctx context.Context, tableID string) error {
	_, err := s.q.CloseAgentSessionsByTableID(ctx, tableID)
	return err
}

func (s *Store) MarkTableStatusByID(ctx context.Context, tableID, status string) error {
	rows, err := s.q.MarkTableStatusByID(ctx, sqlcgen.MarkTableStatusByIDParams{
		ID:     tableID,
		Status: status,
	})
	if err != nil {
		return err
	}
	if rows == 0 {
		return ErrNotFound
	}
	return nil
}

func (s *Store) InsertAgentActionRequest(ctx context.Context, req AgentActionRequest) (bool, error) {
	if req.ID == "" {
		req.ID = NewID()
	}
	rows, err := s.q.InsertAgentActionRequestIfAbsent(ctx, sqlcgen.InsertAgentActionRequestIfAbsentParams{
		ID:         req.ID,
		SessionID:  req.SessionID,
		RequestID:  req.RequestID,
		TurnID:     req.TurnID,
		ActionType: req.Action,
		AmountCc:   int8PtrParam(req.AmountCC),
		ThoughtLog: req.ThoughtLog,
		Accepted:   req.Accepted,
		Reason:     req.Reason,
	})
	if err != nil {
		return false, err
	}
	return rows > 0, nil
}

func (s *Store) GetAgentActionRequest(ctx context.Context, sessionID, requestID string) (*AgentActionRequest, error) {
	r, err := s.q.GetAgentActionRequestBySessionAndRequest(ctx, sqlcgen.GetAgentActionRequestBySessionAndRequestParams{
		SessionID: sessionID,
		RequestID: requestID,
	})
	if err != nil {
		return nil, mapNotFound(err)
	}
	return &AgentActionRequest{
		ID:         r.ID,
		SessionID:  r.SessionID,
		RequestID:  r.RequestID,
		TurnID:     r.TurnID,
		Action:     r.ActionType,
		AmountCC:   int64PtrVal(r.AmountCc),
		ThoughtLog: textVal(r.ThoughtLog),
		Accepted:   r.Accepted,
		Reason:     textVal(r.Reason),
		CreatedAt:  r.CreatedAt.Time,
	}, nil
}

func (s *Store) CountAgentActionRequestsBySessionAndRequest(ctx context.Context, sessionID, requestID string) (int, error) {
	count, err := s.q.CountAgentActionRequestsBySessionAndRequest(ctx, sqlcgen.CountAgentActionRequestsBySessionAndRequestParams{
		SessionID: sessionID,
		RequestID: requestID,
	})
	return int(count), err
}

func (s *Store) UpsertAgentEventOffset(ctx context.Context, sessionID, lastEventID string) error {
	return s.q.UpsertAgentEventOffset(ctx, sqlcgen.UpsertAgentEventOffsetParams{
		SessionID:   sessionID,
		LastEventID: lastEventID,
	})
}

func (s *Store) GetAgentEventOffset(ctx context.Context, sessionID string) (*AgentEventOffset, error) {
	r, err := s.q.GetAgentEventOffsetBySessionID(ctx, sessionID)
	if err != nil {
		return nil, mapNotFound(err)
	}
	return &AgentEventOffset{
		SessionID:   r.SessionID,
		LastEventID: r.LastEventID,
		UpdatedAt:   r.UpdatedAt.Time,
	}, nil
}

func (s *Store) DebugSessionCount(ctx context.Context) (int, error) {
	count, err := s.q.CountAgentSessions(ctx)
	return int(count), err
}
