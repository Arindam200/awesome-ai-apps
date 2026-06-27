package spectatorgateway

import (
	"net/http"
	"time"

	"silicon-casino/internal/agentgateway"
)

var pingInterval = 15 * time.Second

func EventsHandler(coord *agentgateway.Coordinator) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		roomID := r.URL.Query().Get("room_id")
		tableID := r.URL.Query().Get("table_id")
		buf, err := coord.GetPublicBuffer(tableID, roomID)
		if err != nil {
			w.WriteHeader(http.StatusNotFound)
			_, _ = w.Write([]byte(`{"error":"table_not_found"}`))
			return
		}
		flusher, ok := w.(http.Flusher)
		if !ok {
			w.WriteHeader(http.StatusInternalServerError)
			_, _ = w.Write([]byte(`{"error":"stream_not_supported"}`))
			return
		}

		metricSpectatorSSEConnectionsTotal.Add(1)
		metricSpectatorSSEConnectionsActive.Add(1)
		defer metricSpectatorSSEConnectionsActive.Add(-1)

		agentgateway.SetSSEHeaders(w)

		lastEventID := r.Header.Get("Last-Event-ID")
		replay := buf.ReplayAfter(lastEventID)
		for _, ev := range replay {
			if err := agentgateway.WriteSSE(w, ev); err != nil {
				return
			}
		}
		flusher.Flush()

		ch := buf.Subscribe()
		defer buf.Unsubscribe(ch)
		ticker := time.NewTicker(pingInterval)
		defer ticker.Stop()

		for {
			select {
			case <-r.Context().Done():
				return
			case ev, ok := <-ch:
				if !ok {
					return
				}
				if err := agentgateway.WriteSSE(w, ev); err != nil {
					return
				}
				flusher.Flush()
			case <-ticker.C:
				ping := agentgateway.StreamEvent{
					Event:    "ping",
					ServerTS: time.Now().UnixMilli(),
					Data:     map[string]any{"ts": time.Now().UnixMilli()},
				}
				if err := agentgateway.WriteSSE(w, ping); err != nil {
					return
				}
				flusher.Flush()
			}
		}
	}
}
