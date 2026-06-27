package runtime

import (
	"context"
	"encoding/json"
	"time"

	"silicon-casino/internal/game/viewmodel"

	"github.com/rs/zerolog/log"
)

const (
	replaySchemaVersion     int32 = 1
	defaultSnapshotInterval int32 = 80
)

func (c *Coordinator) initReplayRuntime(ctx context.Context, rt *tableRuntime) {
	if c == nil || c.store == nil || rt == nil {
		return
	}
	lastSeq, err := c.store.GetTableReplayLastSeq(ctx, rt.id)
	if err != nil {
		log.Error().Err(err).Str("table_id", rt.id).Msg("load replay last seq failed")
		lastSeq = 0
	}
	rt.globalSeq = lastSeq
	rt.handSeq = 0
	rt.eventsSinceSnapshot = 0
	rt.snapshotInterval = defaultSnapshotInterval

	c.appendReplayEvent(ctx, rt, "table_started", "", map[string]any{
		"table_id": rt.id,
		"room_id":  rt.room.ID,
	})
	c.appendReplayEvent(ctx, rt, "hand_started", "", map[string]any{
		"hand_id": rt.engine.State.HandID,
		"street":  string(rt.engine.State.Street),
	})
	c.appendReplayEvent(ctx, rt, "state_snapshot", "", c.buildReplayState(rt))
}

func (c *Coordinator) appendReplayEvent(ctx context.Context, rt *tableRuntime, eventType, actorAgentID string, payload map[string]any) {
	if c == nil || c.store == nil || rt == nil {
		return
	}
	if payload == nil {
		payload = map[string]any{}
	}
	payload["server_ts"] = time.Now().UnixMilli()
	raw, err := json.Marshal(payload)
	if err != nil {
		log.Error().Err(err).Str("table_id", rt.id).Str("event_type", eventType).Msg("marshal replay payload failed")
		return
	}
	rt.globalSeq++
	hs := rt.handSeq
	if err := c.store.InsertTableReplayEvent(
		ctx,
		rt.id,
		rt.engine.State.HandID,
		rt.globalSeq,
		&hs,
		eventType,
		actorAgentID,
		raw,
		replaySchemaVersion,
	); err != nil {
		log.Error().Err(err).Str("table_id", rt.id).Int64("global_seq", rt.globalSeq).Str("event_type", eventType).Msg("insert replay event failed")
		return
	}
	rt.handSeq++
	rt.eventsSinceSnapshot++
	if rt.snapshotInterval > 0 && rt.eventsSinceSnapshot >= int(rt.snapshotInterval) {
		stateRaw, err := json.Marshal(c.buildReplayState(rt))
		if err != nil {
			log.Error().Err(err).Str("table_id", rt.id).Msg("marshal replay snapshot failed")
			return
		}
		if err := c.store.InsertTableReplaySnapshot(ctx, rt.id, rt.globalSeq, stateRaw, replaySchemaVersion); err != nil {
			log.Error().Err(err).Str("table_id", rt.id).Int64("at_global_seq", rt.globalSeq).Msg("insert replay snapshot failed")
			return
		}
		rt.eventsSinceSnapshot = 0
	}
}

func (c *Coordinator) buildReplayState(rt *tableRuntime) map[string]any {
	state := viewmodel.BuildPublicState(rt.engine.State)
	seatMap := make([]map[string]any, 0, len(rt.players))
	for _, player := range rt.players {
		if player == nil || player.agent == nil {
			continue
		}
		seatMap = append(seatMap, map[string]any{
			"seat_id":    player.seat,
			"agent_id":   player.agent.ID,
			"agent_name": player.agent.Name,
		})
	}
	return map[string]any{
		"table_id":              rt.id,
		"hand_id":               rt.engine.State.HandID,
		"turn_id":               rt.turnID,
		"table_status":          rt.status,
		"close_reason":          rt.closeReason,
		"reconnect_deadline_ts": rt.reconnectDeadline.UnixMilli(),
		"street":                state.Street,
		"pot_cc":                state.Pot,
		"board_cards":           state.CommunityCards,
		"current_actor_seat":    state.CurrentActorSeat,
		"stacks":                state.Seats,
		"seat_map":              seatMap,
	}
}

func buildShowdownPayload(rt *tableRuntime) []map[string]any {
	if rt == nil || rt.engine == nil || rt.engine.State == nil {
		return nil
	}
	out := make([]map[string]any, 0, len(rt.engine.State.Players))
	for _, p := range rt.engine.State.Players {
		if p == nil {
			continue
		}
		cards := make([]string, 0, len(p.Hole))
		for _, c := range p.Hole {
			cards = append(cards, c.String())
		}
		out = append(out, map[string]any{
			"agent_id":   p.ID,
			"seat_id":    p.Seat,
			"hole_cards": cards,
			"stack":      p.Stack,
		})
	}
	return out
}
