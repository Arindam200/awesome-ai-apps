package spectatorgateway

import (
	"encoding/json"
	"net/http"

	"silicon-casino/internal/agentgateway"
)

func StateHandler(coord *agentgateway.Coordinator) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		tableID := r.URL.Query().Get("table_id")
		if tableID == "" {
			w.WriteHeader(http.StatusBadRequest)
			_ = json.NewEncoder(w).Encode(map[string]any{"error": "table_id_required"})
			return
		}
		state, err := coord.GetPublicState(tableID)
		if err != nil {
			w.WriteHeader(http.StatusNotFound)
			_ = json.NewEncoder(w).Encode(map[string]any{"error": "table_not_found"})
			return
		}
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(state)
	}
}
