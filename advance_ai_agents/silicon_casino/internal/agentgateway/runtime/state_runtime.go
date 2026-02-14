package runtime

import "silicon-casino/internal/game/viewmodel"

func (c *Coordinator) GetState(sessionID string) (viewmodel.AgentStateView, error) {
	c.mu.Lock()
	sess := c.sessions[sessionID]
	if sess == nil || sess.runtime == nil {
		c.mu.Unlock()
		return viewmodel.AgentStateView{}, errSessionNotFound
	}
	rt := sess.runtime
	c.mu.Unlock()

	rt.mu.Lock()
	defer rt.mu.Unlock()
	state := viewmodel.BuildAgentState(rt.engine.State, sess.seat, rt.turnID, false)
	state.TableStatus = rt.status
	state.ReconnectDeadlineTS = rt.reconnectDeadline.UnixMilli()
	state.CloseReason = rt.closeReason
	return state, nil
}
