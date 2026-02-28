package runtime

import (
	"time"

	"silicon-casino/internal/game/viewmodel"
)

func (c *Coordinator) emitStateSnapshot(sess *sessionState) {
	if sess == nil || sess.runtime == nil || sess.buffer == nil {
		return
	}
	rt := sess.runtime
	state := viewmodel.BuildAgentState(rt.engine.State, sess.seat, rt.turnID, false)
	state.TableStatus = rt.status
	state.ReconnectDeadlineTS = rt.reconnectDeadline.UnixMilli()
	state.CloseReason = rt.closeReason
	sess.buffer.Append("state_snapshot", sess.session.ID, state)
}

func (c *Coordinator) emitTurnStarted(rt *tableRuntime) {
	if rt == nil {
		return
	}
	if rt.status != tableStatusActive {
		return
	}
	actorSeat := rt.engine.State.CurrentActor
	allowedActions := []string{}
	actorState := viewmodel.BuildAgentState(rt.engine.State, actorSeat, rt.turnID, false)
	rt.turnSeat = actorSeat
	rt.turnDeadline = time.Now().Add(rt.engine.State.ActionTimeout)
	deadlineMS := rt.engine.State.ActionTimeout.Milliseconds()
	turnID := rt.turnID
	handID := rt.engine.State.HandID
	if len(actorState.LegalActions) > 0 {
		allowedActions = actorState.LegalActions
	}
	for _, sess := range rt.players {
		if sess == nil || sess.buffer == nil {
			continue
		}
		sess.buffer.Append("turn_started", sess.session.ID, map[string]any{
			"hand_id":         handID,
			"turn_id":         turnID,
			"seat_id":         actorSeat,
			"deadline_ms":     deadlineMS,
			"allowed_actions": allowedActions,
		})
	}
}

func (c *Coordinator) emitPublicSnapshot(rt *tableRuntime) {
	if rt == nil || rt.publicBuffer == nil {
		return
	}
	state := viewmodel.BuildPublicState(rt.engine.State)
	state.TableStatus = rt.status
	state.ReconnectDeadlineTS = rt.reconnectDeadline.UnixMilli()
	state.CloseReason = rt.closeReason
	rt.publicBuffer.Append("table_snapshot", rt.id, state)
}

func (c *Coordinator) emitPublicActionLog(rt *tableRuntime, seat int, action string, amount *int64, thoughtLog string) {
	if rt == nil || rt.publicBuffer == nil {
		return
	}
	rt.publicBuffer.Append("action_log", rt.id, map[string]any{
		"player_seat": seat,
		"action":      action,
		"amount":      amount,
		"thought_log": thoughtLog,
		"event":       "action",
	})
}
