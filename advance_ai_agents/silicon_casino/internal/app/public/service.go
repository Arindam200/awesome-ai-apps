package public

import (
	"context"
	"encoding/json"
	"errors"
	"time"

	"silicon-casino/internal/store"
)

type Service struct {
	store *store.Store
}

const leaderboardMaxRows = 100

func NewService(st *store.Store) *Service {
	return &Service{store: st}
}

func (s *Service) Rooms(ctx context.Context) (*RoomsResponse, error) {
	items, err := s.store.ListRooms(ctx)
	if err != nil {
		return nil, err
	}
	out := make([]RoomItem, 0, len(items))
	for _, it := range items {
		out = append(out, RoomItem{
			ID:           it.ID,
			Name:         it.Name,
			MinBuyinCC:   it.MinBuyinCC,
			SmallBlindCC: it.SmallBlindCC,
			BigBlindCC:   it.BigBlindCC,
		})
	}
	return &RoomsResponse{Items: out}, nil
}

func (s *Service) Tables(ctx context.Context, roomID string, limit, offset int) (*TablesResponse, error) {
	items, err := s.store.ListTables(ctx, roomID, limit, offset)
	if err != nil {
		return nil, err
	}
	out := make([]TableItem, 0, len(items))
	for _, it := range items {
		out = append(out, TableItem{
			TableID:      it.ID,
			RoomID:       it.RoomID,
			Status:       it.Status,
			CreatedAt:    it.CreatedAt,
			SmallBlindCC: it.SmallBlindCC,
			BigBlindCC:   it.BigBlindCC,
		})
	}
	return &TablesResponse{Items: out, Limit: limit, Offset: offset}, nil
}

func (s *Service) TableHistory(ctx context.Context, roomID, agentID string, limit, offset int) (*TableHistoryResponse, error) {
	total, err := s.store.CountTableHistoryByScope(ctx, roomID, agentID)
	if err != nil {
		return nil, err
	}
	items, err := s.store.ListTableHistory(ctx, roomID, agentID, limit, offset)
	if err != nil {
		return nil, err
	}
	out := make([]TableHistoryItem, 0, len(items))
	for _, it := range items {
		participants := make([]TableHistoryParticipant, 0, len(it.Participants))
		for _, p := range it.Participants {
			participants = append(participants, TableHistoryParticipant{
				AgentID:   p.AgentID,
				AgentName: p.AgentName,
			})
		}
		out = append(out, TableHistoryItem{
			TableID:       it.TableID,
			RoomID:        it.RoomID,
			RoomName:      it.RoomName,
			Status:        it.Status,
			SmallBlindCC:  it.SmallBlindCC,
			BigBlindCC:    it.BigBlindCC,
			HandsPlayed:   it.HandsPlayed,
			Participants:  participants,
			CreatedAt:     it.CreatedAt,
			LastHandEnded: it.LastHandEnded,
		})
	}
	return &TableHistoryResponse{Items: out, Total: total, Limit: limit, Offset: offset}, nil
}

func (s *Service) AgentTables(ctx context.Context, agentID string, limit, offset int) (*TableHistoryResponse, error) {
	if agentID == "" {
		return nil, ErrInvalidRequest
	}
	items, err := s.store.ListAgentTables(ctx, agentID, limit, offset)
	if err != nil {
		return nil, err
	}
	out := make([]TableHistoryItem, 0, len(items))
	for _, it := range items {
		out = append(out, TableHistoryItem{
			TableID:       it.TableID,
			RoomID:        it.RoomID,
			RoomName:      it.RoomName,
			Status:        it.Status,
			SmallBlindCC:  it.SmallBlindCC,
			BigBlindCC:    it.BigBlindCC,
			HandsPlayed:   it.HandsPlayed,
			CreatedAt:     it.CreatedAt,
			LastHandEnded: it.LastHandEnded,
		})
	}
	return &TableHistoryResponse{Items: out, Total: len(out), Limit: limit, Offset: offset}, nil
}

func (s *Service) AgentProfile(ctx context.Context, agentID string, limit, offset int) (*AgentProfileResponse, error) {
	if agentID == "" {
		return nil, ErrInvalidRequest
	}
	agent, err := s.store.GetAgentByID(ctx, agentID)
	if err != nil {
		if errors.Is(err, store.ErrNotFound) {
			return nil, ErrNotFound
		}
		return nil, err
	}
	window30d := leaderboardWindowStart("30d")
	stats30d, err := s.store.GetAgentPerformanceByWindowAndAgent(ctx, agentID, window30d)
	if err != nil {
		return nil, err
	}
	statsAll, err := s.store.GetAgentPerformanceByWindowAndAgent(ctx, agentID, nil)
	if err != nil {
		return nil, err
	}
	total, err := s.store.CountTableHistoryByScope(ctx, "", agentID)
	if err != nil {
		return nil, err
	}
	items, err := s.store.ListTableHistory(ctx, "", agentID, limit, offset)
	if err != nil {
		return nil, err
	}
	out := make([]TableHistoryItem, 0, len(items))
	for _, it := range items {
		participants := make([]TableHistoryParticipant, 0, len(it.Participants))
		for _, p := range it.Participants {
			participants = append(participants, TableHistoryParticipant{
				AgentID:   p.AgentID,
				AgentName: p.AgentName,
			})
		}
		out = append(out, TableHistoryItem{
			TableID:       it.TableID,
			RoomID:        it.RoomID,
			RoomName:      it.RoomName,
			Status:        it.Status,
			SmallBlindCC:  it.SmallBlindCC,
			BigBlindCC:    it.BigBlindCC,
			HandsPlayed:   it.HandsPlayed,
			Participants:  participants,
			CreatedAt:     it.CreatedAt,
			LastHandEnded: it.LastHandEnded,
		})
	}
	return &AgentProfileResponse{
		Agent: AgentIdentity{
			AgentID:   agent.ID,
			Name:      agent.Name,
			CreatedAt: agent.CreatedAt,
		},
		Stats30D: AgentPerformanceSnapshot{
			Score:         stats30d.Score,
			BBPer100:      stats30d.BBPer100,
			NetCCFromPlay: stats30d.NetCCFromPlay,
			HandsPlayed:   stats30d.HandsPlayed,
			WinRate:       stats30d.WinRate,
			LastActiveAt:  stats30d.LastActiveAt,
		},
		StatsAll: AgentPerformanceSnapshot{
			Score:         statsAll.Score,
			BBPer100:      statsAll.BBPer100,
			NetCCFromPlay: statsAll.NetCCFromPlay,
			HandsPlayed:   statsAll.HandsPlayed,
			WinRate:       statsAll.WinRate,
			LastActiveAt:  statsAll.LastActiveAt,
		},
		Tables: TableHistoryResponse{
			Items:  out,
			Total:  total,
			Limit:  limit,
			Offset: offset,
		},
	}, nil
}

func (s *Service) TableReplay(ctx context.Context, tableID string, fromSeq int64, limit int) (*ReplayResponse, error) {
	if tableID == "" {
		return nil, ErrInvalidRequest
	}
	lastSeq, err := s.store.GetTableReplayLastSeq(ctx, tableID)
	if err != nil {
		return nil, err
	}
	if lastSeq == 0 {
		return nil, ErrTableNotFound
	}
	items, err := s.store.ListTableReplayEventsFromSeq(ctx, tableID, fromSeq, limit)
	if err != nil {
		return nil, err
	}
	out := make([]ReplayEvent, 0, len(items))
	for _, it := range items {
		var payload any
		if len(it.Payload) > 0 {
			_ = json.Unmarshal(it.Payload, &payload)
		}
		out = append(out, ReplayEvent{
			ID:           it.ID,
			TableID:      it.TableID,
			HandID:       it.HandID,
			GlobalSeq:    it.GlobalSeq,
			HandSeq:      it.HandSeq,
			EventType:    it.EventType,
			ActorAgentID: it.ActorAgentID,
			Payload:      payload,
			SchemaVer:    it.SchemaVer,
			CreatedAt:    it.CreatedAt,
		})
	}
	nextFrom := fromSeq + int64(len(out))
	return &ReplayResponse{
		Items:       out,
		NextFromSeq: nextFrom,
		HasMore:     nextFrom <= lastSeq,
		LastSeq:     lastSeq,
	}, nil
}

func (s *Service) TableTimeline(ctx context.Context, tableID string) (*TimelineResponse, error) {
	if tableID == "" {
		return nil, ErrInvalidRequest
	}
	hands, err := s.store.ListHandsByTableID(ctx, tableID)
	if err != nil {
		return nil, err
	}
	lastSeq, err := s.store.GetTableReplayLastSeq(ctx, tableID)
	if err != nil {
		return nil, err
	}
	if lastSeq == 0 {
		return nil, ErrTableNotFound
	}
	events, err := s.store.ListTableReplayEventsFromSeq(ctx, tableID, 1, int(lastSeq))
	if err != nil {
		return nil, err
	}
	byHandSeqRange := make(map[string]map[string]int64)
	for _, ev := range events {
		if ev.HandID == "" {
			continue
		}
		rng := byHandSeqRange[ev.HandID]
		if rng == nil {
			rng = map[string]int64{"start": ev.GlobalSeq, "end": ev.GlobalSeq}
			byHandSeqRange[ev.HandID] = rng
		}
		if ev.GlobalSeq < rng["start"] {
			rng["start"] = ev.GlobalSeq
		}
		if ev.GlobalSeq > rng["end"] {
			rng["end"] = ev.GlobalSeq
		}
	}
	out := make([]TimelineItem, 0, len(hands))
	for _, h := range hands {
		rng := byHandSeqRange[h.ID]
		startSeq := int64(0)
		endSeq := int64(0)
		if rng != nil {
			startSeq = rng["start"]
			endSeq = rng["end"]
		}
		out = append(out, TimelineItem{
			HandID:        h.ID,
			StartSeq:      startSeq,
			EndSeq:        endSeq,
			WinnerAgentID: h.WinnerAgentID,
			PotCC:         h.PotCC,
			StreetEnd:     h.StreetEnd,
			StartedAt:     h.StartedAt,
			EndedAt:       h.EndedAt,
		})
	}
	return &TimelineResponse{TableID: tableID, Items: out}, nil
}

func (s *Service) TableSnapshot(ctx context.Context, tableID string, atSeq int64) (*SnapshotResponse, error) {
	if tableID == "" || atSeq < 1 {
		return nil, ErrInvalidRequest
	}
	lastSeq, err := s.store.GetTableReplayLastSeq(ctx, tableID)
	if err != nil {
		return nil, err
	}
	if lastSeq == 0 {
		return nil, ErrTableNotFound
	}
	if atSeq > lastSeq {
		atSeq = lastSeq
	}
	snap, err := s.store.GetLatestTableReplaySnapshotAtOrBefore(ctx, tableID, atSeq)
	snapshotSeq := int64(0)
	replayState := map[string]any{}
	hit := false
	if err == nil && snap != nil {
		hit = true
		snapshotSeq = snap.AtGlobalSeq
		_ = json.Unmarshal(snap.StateBlob, &replayState)
	}
	fromSeq := snapshotSeq + 1
	limit := int(atSeq - snapshotSeq + 1)
	if limit < 1 {
		limit = 1
	}
	events, err := s.store.ListTableReplayEventsFromSeq(ctx, tableID, fromSeq, limit)
	if err != nil {
		return nil, err
	}
	for _, ev := range events {
		if ev.GlobalSeq > atSeq {
			break
		}
		var payload map[string]any
		if err := json.Unmarshal(ev.Payload, &payload); err != nil {
			continue
		}
		if ev.EventType == "state_snapshot" {
			replayState = payload
		}
		replayState["last_event_type"] = ev.EventType
		replayState["global_seq"] = ev.GlobalSeq
	}
	return &SnapshotResponse{TableID: tableID, AtSeq: atSeq, State: replayState, Hit: hit}, nil
}

func (s *Service) Leaderboard(ctx context.Context, q LeaderboardQuery, limit, offset int) (*LeaderboardResponse, error) {
	windowStart := leaderboardWindowStart(q.Window)
	allItems, err := s.store.ListLeaderboard(ctx, store.LeaderboardFilter{
		WindowStart: windowStart,
		RoomScope:   q.RoomID,
		SortBy:      q.SortBy,
	}, leaderboardMaxRows, 0)
	if err != nil {
		return nil, err
	}
	total := len(allItems)
	limit, ok := clampLeaderboardPage(limit, offset)
	if !ok || offset >= total {
		return &LeaderboardResponse{Items: []LeaderboardItem{}, Total: total, Limit: limit, Offset: offset}, nil
	}
	end := offset + limit
	if end > total {
		end = total
	}
	pageItems := allItems[offset:end]
	out := make([]LeaderboardItem, 0, len(pageItems))
	for idx, it := range pageItems {
		out = append(out, LeaderboardItem{
			Rank:          offset + idx + 1,
			AgentID:       it.AgentID,
			Name:          it.Name,
			Score:         it.Score,
			BBPer100:      it.BBPer100,
			NetCCFromPlay: it.NetCCFromPlay,
			HandsPlayed:   it.HandsPlayed,
			WinRate:       it.WinRate,
			LastActiveAt:  it.LastActiveAt,
		})
	}
	return &LeaderboardResponse{Items: out, Total: total, Limit: limit, Offset: offset}, nil
}

func leaderboardWindowStart(window string) *time.Time {
	now := time.Now().UTC()
	switch window {
	case "7d":
		ts := now.Add(-7 * 24 * time.Hour)
		return &ts
	case "30d":
		ts := now.Add(-30 * 24 * time.Hour)
		return &ts
	default:
		return nil
	}
}

func clampLeaderboardPage(limit, offset int) (int, bool) {
	if offset >= leaderboardMaxRows {
		return 0, false
	}
	if limit <= 0 {
		limit = 50
	}
	remaining := leaderboardMaxRows - offset
	if limit > remaining {
		limit = remaining
	}
	return limit, true
}
