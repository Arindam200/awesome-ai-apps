package agentgateway

import (
	"encoding/json"
	"errors"
	"net/http"

	"silicon-casino/internal/game/viewmodel"

	"github.com/go-chi/chi/v5"
)

func StateHandler(coord *Coordinator) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		sessionID := chi.URLParam(r, "session_id")
		if sessionID == "" {
			writeErr(w, http.StatusBadRequest, "session_not_found")
			return
		}
		state, err := coord.GetState(sessionID)
		if err != nil {
			if errors.Is(err, errSessionNotFound) {
				writeErr(w, http.StatusNotFound, "session_not_found")
				return
			}
			writeErr(w, http.StatusInternalServerError, "internal_error")
			return
		}
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(state)
	}
}

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
