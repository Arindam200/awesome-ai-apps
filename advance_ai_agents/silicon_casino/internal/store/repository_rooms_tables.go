package store

import (
	"context"

	"silicon-casino/internal/store/sqlcgen"
)

func (s *Store) CreateTable(ctx context.Context, roomID, status string, sb, bb int64) (string, error) {
	id := NewID()
	err := s.q.CreateTable(ctx, sqlcgen.CreateTableParams{
		ID:           id,
		RoomID:       textParam(roomID),
		Status:       status,
		SmallBlindCc: sb,
		BigBlindCc:   bb,
	})
	return id, err
}

func (s *Store) ListTables(ctx context.Context, roomID string, limit, offset int) ([]Table, error) {
	if limit <= 0 {
		limit = 50
	}
	rows, err := s.q.ListTables(ctx, sqlcgen.ListTablesParams{
		RoomID:     roomID,
		LimitRows:  int32(limit),
		OffsetRows: int32(offset),
	})
	if err != nil {
		return nil, err
	}
	out := make([]Table, 0, len(rows))
	for _, r := range rows {
		out = append(out, Table{
			ID:           r.ID,
			RoomID:       textVal(r.RoomID),
			Status:       r.Status,
			SmallBlindCC: r.SmallBlindCc,
			BigBlindCC:   r.BigBlindCc,
			CreatedAt:    r.CreatedAt.Time,
		})
	}
	return out, nil
}

func (s *Store) CreateHand(ctx context.Context, tableID string) (string, error) {
	id := NewID()
	err := s.q.CreateHand(ctx, sqlcgen.CreateHandParams{ID: id, TableID: tableID})
	return id, err
}

func (s *Store) EndHand(ctx context.Context, handID string) error {
	return s.q.EndHand(ctx, sqlcgen.EndHandParams{
		HandID:        handID,
		WinnerAgentID: "",
		PotCc:         int8PtrParam(nil),
		StreetEnd:     "",
	})
}

func (s *Store) EndHandWithSummary(ctx context.Context, handID, winnerAgentID string, potCC *int64, streetEnd string) error {
	return s.q.EndHand(ctx, sqlcgen.EndHandParams{
		HandID:        handID,
		WinnerAgentID: winnerAgentID,
		PotCc:         int8PtrParam(potCC),
		StreetEnd:     streetEnd,
	})
}

func (s *Store) RecordAction(ctx context.Context, handID, agentID, actionType string, amount int64) error {
	return s.q.RecordAction(ctx, sqlcgen.RecordActionParams{
		ID:         NewID(),
		HandID:     handID,
		AgentID:    agentID,
		ActionType: actionType,
		AmountCc:   amount,
	})
}

func (s *Store) ListRooms(ctx context.Context) ([]Room, error) {
	rows, err := s.q.ListRooms(ctx)
	if err != nil {
		return nil, err
	}
	out := make([]Room, 0, len(rows))
	for _, r := range rows {
		out = append(out, Room{
			ID:           r.ID,
			Name:         r.Name,
			MinBuyinCC:   r.MinBuyinCc,
			SmallBlindCC: r.SmallBlindCc,
			BigBlindCC:   r.BigBlindCc,
			Status:       r.Status,
			CreatedAt:    r.CreatedAt.Time,
		})
	}
	return out, nil
}

func (s *Store) GetRoom(ctx context.Context, id string) (*Room, error) {
	r, err := s.q.GetRoomByID(ctx, id)
	if err != nil {
		return nil, mapNotFound(err)
	}
	return &Room{
		ID:           r.ID,
		Name:         r.Name,
		MinBuyinCC:   r.MinBuyinCc,
		SmallBlindCC: r.SmallBlindCc,
		BigBlindCC:   r.BigBlindCc,
		Status:       r.Status,
		CreatedAt:    r.CreatedAt.Time,
	}, nil
}

func (s *Store) CreateRoom(ctx context.Context, name string, minBuyin, sb, bb int64) (string, error) {
	id := NewID()
	err := s.q.CreateRoom(ctx, sqlcgen.CreateRoomParams{
		ID:           id,
		Name:         name,
		MinBuyinCc:   minBuyin,
		SmallBlindCc: sb,
		BigBlindCc:   bb,
	})
	return id, err
}

func (s *Store) CountRooms(ctx context.Context) (int, error) {
	c, err := s.q.CountRooms(ctx)
	return int(c), err
}

func (s *Store) EnsureDefaultRooms(ctx context.Context) error {
	c, err := s.CountRooms(ctx)
	if err != nil {
		return err
	}
	if c > 0 {
		return nil
	}
	if _, err := s.CreateRoom(ctx, "Low", 1000, 50, 100); err != nil {
		return err
	}
	if _, err := s.CreateRoom(ctx, "Mid", 5000, 100, 200); err != nil {
		return err
	}
	_, err = s.CreateRoom(ctx, "High", 20000, 500, 1000)
	return err
}
