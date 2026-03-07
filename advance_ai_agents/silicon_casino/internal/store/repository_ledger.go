package store

import (
	"context"
	"time"

	"silicon-casino/internal/store/sqlcgen"

	"github.com/jackc/pgx/v5/pgtype"
)

type LedgerFilter struct {
	AgentID string
	HandID  string
	From    *time.Time
	To      *time.Time
}

type LeaderboardFilter struct {
	WindowStart *time.Time
	RoomScope   string
	SortBy      string
}

func (s *Store) ListLedgerEntries(ctx context.Context, f LedgerFilter, limit, offset int) ([]LedgerEntry, error) {
	if limit <= 0 {
		limit = 50
	}
	rows, err := s.q.ListLedgerEntries(ctx, sqlcgen.ListLedgerEntriesParams{
		AgentID:    f.AgentID,
		HandID:     f.HandID,
		FromTs:     timeParam(f.From),
		ToTs:       timeParam(f.To),
		LimitRows:  int32(limit),
		OffsetRows: int32(offset),
	})
	if err != nil {
		return nil, err
	}
	out := make([]LedgerEntry, 0, len(rows))
	for _, r := range rows {
		out = append(out, LedgerEntry{
			ID:        r.ID,
			AgentID:   r.AgentID,
			Type:      r.Type,
			AmountCC:  r.AmountCc,
			RefType:   r.RefType,
			RefID:     r.RefID,
			CreatedAt: r.CreatedAt.Time,
		})
	}
	return out, nil
}

func (s *Store) ListLeaderboard(ctx context.Context, f LeaderboardFilter, limit, offset int) ([]LeaderboardEntry, error) {
	if limit <= 0 {
		limit = 50
	}
	if f.RoomScope == "" {
		f.RoomScope = "all"
	}
	if f.SortBy == "" {
		f.SortBy = "score"
	}
	rows, err := s.q.ListLeaderboard(ctx, sqlcgen.ListLeaderboardParams{
		WindowStart: timeParam(f.WindowStart),
		RoomScope:   f.RoomScope,
		SortBy:      f.SortBy,
		LimitRows:   int32(limit),
		OffsetRows:  int32(offset),
	})
	if err != nil {
		return nil, err
	}
	out := make([]LeaderboardEntry, 0, len(rows))
	for _, r := range rows {
		out = append(out, LeaderboardEntry{
			AgentID:          r.AgentID,
			Name:             r.Name,
			Score:            r.Score,
			BBPer100:         r.BbPer100,
			NetCCFromPlay:    r.NetCcFromPlay,
			HandsPlayed:      int(r.HandsPlayed),
			WinRate:          r.WinRate,
			ConfidenceFactor: r.ConfidenceFactor,
			LastActiveAt:     r.LastActiveAt.Time,
		})
	}
	return out, nil
}

func (s *Store) GetAgentPerformanceByWindowAndAgent(ctx context.Context, agentID string, windowStart *time.Time) (*AgentPerformance, error) {
	row, err := s.q.GetAgentPerformanceByWindowAndAgent(ctx, sqlcgen.GetAgentPerformanceByWindowAndAgentParams{
		AgentID:     agentID,
		WindowStart: timeParam(windowStart),
	})
	if err != nil {
		return nil, mapNotFound(err)
	}
	var lastActiveAt *time.Time
	switch v := row.LastActiveAt.(type) {
	case time.Time:
		vt := v
		lastActiveAt = &vt
	case pgtype.Timestamptz:
		lastActiveAt = timePtrVal(v)
	}
	return &AgentPerformance{
		AgentID:          row.AgentID,
		Score:            row.Score,
		BBPer100:         row.BbPer100,
		NetCCFromPlay:    row.NetCcFromPlay,
		HandsPlayed:      int(row.HandsPlayed),
		WinRate:          row.WinRate,
		ConfidenceFactor: row.ConfidenceFactor,
		LastActiveAt:     lastActiveAt,
	}, nil
}
