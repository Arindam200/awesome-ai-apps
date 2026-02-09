package agentgateway

import (
	"encoding/json"
	"net/http"

	"silicon-casino/internal/store"

	"github.com/go-chi/chi/v5"
)

func SessionsCreateHandler(coord *Coordinator) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		metricSessionCreateTotal.Add(1)
		var req CreateSessionRequest
		if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
			metricSessionCreateErrors.Add(1)
			writeErr(w, http.StatusBadRequest, "invalid_json")
			return
		}
		res, err := coord.CreateSession(r.Context(), req)
		if err != nil {
			metricSessionCreateErrors.Add(1)
			status, code := mapSessionErr(err)
			if code == "agent_already_in_session" {
				if existing, ok := coord.FindOpenSessionByAgent(req.AgentID); ok {
					w.Header().Set("Content-Type", "application/json")
					w.WriteHeader(status)
					_ = json.NewEncoder(w).Encode(struct {
						Error string `json:"error"`
						CreateSessionResponse
					}{
						Error:                 code,
						CreateSessionResponse: *existing,
					})
					return
				}
			}
			writeErr(w, status, code)
			return
		}
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(res)
	}
}

func SessionsDeleteHandler(coord *Coordinator) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		sessionID := chi.URLParam(r, "session_id")
		if sessionID == "" {
			writeErr(w, http.StatusBadRequest, "session_not_found")
			return
		}
		if err := coord.CloseSession(r.Context(), sessionID); err != nil {
			if err == store.ErrNotFound {
				writeErr(w, http.StatusNotFound, "session_not_found")
				return
			}
			writeErr(w, http.StatusInternalServerError, "internal_error")
			return
		}
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(map[string]any{"ok": true})
	}
}

func mapSessionErr(err error) (int, string) {
	switch err.Error() {
	case "invalid_api_key":
		return http.StatusUnauthorized, "invalid_api_key"
	case "room_not_found":
		return http.StatusNotFound, "room_not_found"
	case "insufficient_buyin":
		return http.StatusBadRequest, "insufficient_buyin"
	case "no_available_room":
		return http.StatusBadRequest, "no_available_room"
	case "agent_already_in_session":
		return http.StatusConflict, "agent_already_in_session"
	case "invalid_action":
		return http.StatusBadRequest, "invalid_action"
	default:
		return http.StatusInternalServerError, "internal_error"
	}
}

func writeErr(w http.ResponseWriter, status int, code string) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(ErrorResponse{Error: code})
}
