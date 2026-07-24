package httptransport

import (
	"encoding/json"
	"net/http"

	"silicon-casino/internal/agentgateway"

	"github.com/go-chi/chi/v5"
)

func StateHandler(coord *agentgateway.Coordinator) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		sessionID := chi.URLParam(r, "session_id")
		if sessionID == "" {
			WriteHTTPError(w, http.StatusBadRequest, "session_not_found")
			return
		}
		state, err := coord.GetState(sessionID)
		if err != nil {
			if agentgateway.IsSessionNotFound(err) {
				WriteHTTPError(w, http.StatusNotFound, "session_not_found")
				return
			}
			WriteHTTPError(w, http.StatusInternalServerError, "internal_error")
			return
		}
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(state)
	}
}
