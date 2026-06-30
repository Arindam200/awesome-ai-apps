package store

import (
	"context"
	"encoding/json"
	"time"

	"silicon-casino/internal/store/sqlcgen"

	"github.com/jackc/pgx/v5/pgtype"
)

func (s *Store) InsertTableReplayEvent(
	ctx context.Context,
	tableID, handID string,
	globalSeq int64,
	handSeq *int32,
	eventType, actorAgentID string,
	payload json.RawMessage,
	schemaVersion int32,
) error {
	return s.q.InsertTableReplayEvent(ctx, sqlcgen.InsertTableReplayEventParams{
		ID:            NewID(),
		TableID:       tableID,
		HandID:        handID,
		GlobalSeq:     globalSeq,
		HandSeq:       int32PtrParam(handSeq),
		EventType:     eventType,
		ActorAgentID:  actorAgentID,
		Payload:       payload,
		SchemaVersion: schemaVersion,
	})
}

func (s *Store) ListTableReplayEventsFromSeq(ctx context.Context, tableID string, fromSeq int64, limit int) ([]TableReplayEvent, error) {
	if limit <= 0 {
		limit = 200
	}
	rows, err := s.q.ListTableReplayEventsFromSeq(ctx, sqlcgen.ListTableReplayEventsFromSeqParams{
		TableID:   tableID,
		GlobalSeq: fromSeq,
		Limit:     int32(limit),
	})
	if err != nil {
		return nil, err
	}
	out := make([]TableReplayEvent, 0, len(rows))
	for _, r := range rows {
		out = append(out, TableReplayEvent{
			ID:           r.ID,
			TableID:      r.TableID,
			HandID:       textVal(r.HandID),
			GlobalSeq:    r.GlobalSeq,
			HandSeq:      int32PtrVal(r.HandSeq),
			EventType:    r.EventType,
			ActorAgentID: textVal(r.ActorAgentID),
			Payload:      r.Payload,
			SchemaVer:    r.SchemaVersion,
			CreatedAt:    r.CreatedAt.Time,
		})
	}
	return out, nil
}

func (s *Store) GetTableReplayLastSeq(ctx context.Context, tableID string) (int64, error) {
	return s.q.GetTableReplayLastSeq(ctx, tableID)
}

func (s *Store) InsertTableReplaySnapshot(
	ctx context.Context,
	tableID string,
	atGlobalSeq int64,
	stateBlob json.RawMessage,
	schemaVersion int32,
) error {
	return s.q.InsertTableReplaySnapshot(ctx, sqlcgen.InsertTableReplaySnapshotParams{
		ID:            NewID(),
		TableID:       tableID,
		AtGlobalSeq:   atGlobalSeq,
		StateBlob:     stateBlob,
		SchemaVersion: schemaVersion,
	})
}

func (s *Store) GetLatestTableReplaySnapshotAtOrBefore(ctx context.Context, tableID string, atSeq int64) (*TableReplaySnapshot, error) {
	r, err := s.q.GetLatestTableReplaySnapshotAtOrBefore(ctx, sqlcgen.GetLatestTableReplaySnapshotAtOrBeforeParams{
		TableID:     tableID,
		AtGlobalSeq: atSeq,
	})
	if err != nil {
		return nil, mapNotFound(err)
	}
	return &TableReplaySnapshot{
		ID:          r.ID,
		TableID:     r.TableID,
		AtGlobalSeq: r.AtGlobalSeq,
		StateBlob:   r.StateBlob,
		SchemaVer:   r.SchemaVersion,
		CreatedAt:   r.CreatedAt.Time,
	}, nil
}

func (s *Store) ListHandsByTableID(ctx context.Context, tableID string) ([]Hand, error) {
	rows, err := s.q.ListHandsByTableID(ctx, tableID)
	if err != nil {
		return nil, err
	}
	out := make([]Hand, 0, len(rows))
	for _, r := range rows {
		out = append(out, Hand{
			ID:            r.ID,
			TableID:       r.TableID,
			WinnerAgentID: textVal(r.WinnerAgentID),
			PotCC:         int64PtrVal(r.PotCc),
			StreetEnd:     textVal(r.StreetEnd),
			StartedAt:     r.StartedAt.Time,
			EndedAt:       timePtrVal(r.EndedAt),
		})
	}
	return out, nil
}

func (s *Store) GetHandByID(ctx context.Context, handID string) (*Hand, error) {
	r, err := s.q.GetHandByID(ctx, handID)
	if err != nil {
		return nil, mapNotFound(err)
	}
	return &Hand{
		ID:            r.ID,
		TableID:       r.TableID,
		WinnerAgentID: textVal(r.WinnerAgentID),
		PotCC:         int64PtrVal(r.PotCc),
		StreetEnd:     textVal(r.StreetEnd),
		StartedAt:     r.StartedAt.Time,
		EndedAt:       timePtrVal(r.EndedAt),
	}, nil
}

func (s *Store) ListHandsByAgentID(ctx context.Context, agentID string, limit, offset int) ([]Hand, error) {
	if limit <= 0 {
		limit = 50
	}
	rows, err := s.q.ListHandsByAgentID(ctx, sqlcgen.ListHandsByAgentIDParams{
		AgentID: agentID,
		Limit:   int32(limit),
		Offset:  int32(offset),
	})
	if err != nil {
		return nil, err
	}
	out := make([]Hand, 0, len(rows))
	for _, r := range rows {
		out = append(out, Hand{
			ID:            r.ID,
			TableID:       r.TableID,
			WinnerAgentID: textVal(r.WinnerAgentID),
			PotCC:         int64PtrVal(r.PotCc),
			StreetEnd:     textVal(r.StreetEnd),
			StartedAt:     r.StartedAt.Time,
			EndedAt:       timePtrVal(r.EndedAt),
		})
	}
	return out, nil
}

func (s *Store) ListAgentTables(ctx context.Context, agentID string, limit, offset int) ([]AgentTableHistory, error) {
	if limit <= 0 {
		limit = 50
	}
	rows, err := s.q.ListAgentTables(ctx, sqlcgen.ListAgentTablesParams{
		AgentID: agentID,
		Limit:   int32(limit),
		Offset:  int32(offset),
	})
	if err != nil {
		return nil, err
	}
	out := make([]AgentTableHistory, 0, len(rows))
	for _, r := range rows {
		var endedAt *time.Time
		switch v := r.LastHandEndedAt.(type) {
		case time.Time:
			vt := v
			endedAt = &vt
		case pgtype.Timestamptz:
			endedAt = timePtrVal(v)
		}
		out = append(out, AgentTableHistory{
			TableID:       r.ID,
			RoomID:        textVal(r.RoomID),
			Status:        r.Status,
			SmallBlindCC:  r.SmallBlindCc,
			BigBlindCC:    r.BigBlindCc,
			CreatedAt:     r.CreatedAt.Time,
			LastHandEnded: endedAt,
		})
	}
	return out, nil
}

func (s *Store) ListTableHistory(ctx context.Context, roomID, agentID string, limit, offset int) ([]AgentTableHistory, error) {
	if limit <= 0 {
		limit = 50
	}
	rows, err := s.q.ListTableHistory(ctx, sqlcgen.ListTableHistoryParams{
		RoomID:     roomID,
		AgentID:    agentID,
		LimitRows:  int32(limit),
		OffsetRows: int32(offset),
	})
	if err != nil {
		return nil, err
	}
	out := make([]AgentTableHistory, 0, len(rows))
	for _, r := range rows {
		participants := make([]HistoryParticipant, 0, 2)
		if len(r.Participants) > 0 {
			_ = json.Unmarshal(r.Participants, &participants)
		}
		var endedAt *time.Time
		switch v := r.LastHandEndedAt.(type) {
		case time.Time:
			vt := v
			endedAt = &vt
		case pgtype.Timestamptz:
			endedAt = timePtrVal(v)
		}
		out = append(out, AgentTableHistory{
			TableID:       r.ID,
			RoomID:        textVal(r.RoomID),
			RoomName:      r.RoomName,
			Status:        r.Status,
			SmallBlindCC:  r.SmallBlindCc,
			BigBlindCC:    r.BigBlindCc,
			HandsPlayed:   int(r.HandsPlayed),
			Participants:  participants,
			CreatedAt:     r.CreatedAt.Time,
			LastHandEnded: endedAt,
		})
	}
	return out, nil
}

func (s *Store) CountTableHistoryByScope(ctx context.Context, roomID, agentID string) (int, error) {
	count, err := s.q.CountTableHistoryByScope(ctx, sqlcgen.CountTableHistoryByScopeParams{
		RoomID:  roomID,
		AgentID: agentID,
	})
	return int(count), err
}
