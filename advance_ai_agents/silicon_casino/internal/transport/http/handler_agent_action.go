package httptransport

import (
	"encoding/json"
	"net/http"

	"silicon-casino/internal/agentgateway"

	"github.com/go-chi/chi/v5"
)

func ActionsHandler(coord *agentgateway.Coordinator) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		metricActionSubmitTotal.Add(1)
		sessionID := chi.URLParam(r, "session_id")
		if sessionID == "" {
			metricActionSubmitErrors.Add(1)
			WriteHTTPError(w, http.StatusBadRequest, "session_not_found")
			return
		}
		var req agentgateway.ActionRequest
		if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
			metricActionSubmitErrors.Add(1)
			WriteHTTPError(w, http.StatusBadRequest, "invalid_json")
			return
		}
		res, err := coord.SubmitAction(r.Context(), sessionID, req)
		if err != nil {
			metricActionSubmitErrors.Add(1)
			status, code := agentgateway.MapActionSubmitError(err)
			WriteHTTPError(w, status, code)
			return
		}
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(res)
	}
}
