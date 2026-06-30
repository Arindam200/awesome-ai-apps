package httptransport

import (
	"encoding/json"
	"net/http"

	"silicon-casino/internal/agentgateway"
	"silicon-casino/internal/store"

	"github.com/go-chi/chi/v5"
)

func SessionsCreateHandler(coord *agentgateway.Coordinator) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		metricSessionCreateTotal.Add(1)
		var req agentgateway.CreateSessionRequest
		if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
			metricSessionCreateErrors.Add(1)
			WriteHTTPError(w, http.StatusBadRequest, "invalid_json")
			return
		}
		res, err := coord.CreateSession(r.Context(), req)
		if err != nil {
			metricSessionCreateErrors.Add(1)
			status, code := agentgateway.MapSessionCreateError(err)
			if code == "agent_already_in_session" {
				if existing, ok := coord.FindOpenSessionByAgent(req.AgentID); ok {
					w.Header().Set("Content-Type", "application/json")
					w.WriteHeader(status)
					_ = json.NewEncoder(w).Encode(struct {
						Error string `json:"error"`
						agentgateway.CreateSessionResponse
					}{
						Error:                 code,
						CreateSessionResponse: *existing,
					})
					return
				}
			}
			WriteHTTPError(w, status, code)
			return
		}
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(res)
	}
}

func SessionsDeleteHandler(coord *agentgateway.Coordinator) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		sessionID := chi.URLParam(r, "session_id")
		if sessionID == "" {
			WriteHTTPError(w, http.StatusBadRequest, "session_not_found")
			return
		}
		if err := coord.CloseSession(r.Context(), sessionID); err != nil {
			if err == store.ErrNotFound {
				WriteHTTPError(w, http.StatusNotFound, "session_not_found")
				return
			}
			WriteHTTPError(w, http.StatusInternalServerError, "internal_error")
			return
		}
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(map[string]any{"ok": true})
	}
}
