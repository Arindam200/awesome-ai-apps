package httptransport

import (
	"net/http"
	"time"

	"silicon-casino/internal/agentgateway"

	"github.com/go-chi/chi/v5"
	chimw "github.com/go-chi/chi/v5/middleware"
	"github.com/rs/zerolog/log"
)

var ssePingInterval = 15 * time.Second

func EventsSSEHandler(coord *agentgateway.Coordinator) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		sessionID := chi.URLParam(r, "session_id")
		if sessionID == "" {
			WriteHTTPError(w, http.StatusBadRequest, "session_not_found")
			return
		}
		buf := coord.GetSessionBuffer(sessionID)
		if buf == nil {
			WriteHTTPError(w, http.StatusNotFound, "session_not_found")
			return
		}
		flusher, ok := w.(http.Flusher)
		if !ok {
			WriteHTTPError(w, http.StatusInternalServerError, "stream_not_supported")
			return
		}

		metricAgentSSEConnectionsTotal.Add(1)
		metricAgentSSEConnectionsActive.Add(1)
		defer metricAgentSSEConnectionsActive.Add(-1)

		agentgateway.SetSSEHeaders(w)
		log.Info().
			Str("request_id", chimw.GetReqID(r.Context())).
			Str("session_id", sessionID).
			Msg("sse stream opened")

		lastEventID := r.Header.Get("Last-Event-ID")
		if lastEventID == "" {
			if off, err := coord.Store().GetAgentEventOffset(r.Context(), sessionID); err == nil && off.LastEventID != "" {
				lastEventID = off.LastEventID
			}
		}
		replay := buf.ReplayAfter(lastEventID)
		for _, ev := range replay {
			if err := agentgateway.WriteSSE(w, ev); err != nil {
				return
			}
			logSSEEvent(r, sessionID, "replay", ev)
			_ = coord.Store().UpsertAgentEventOffset(r.Context(), sessionID, ev.EventID)
		}
		flusher.Flush()

		ch := buf.Subscribe()
		defer buf.Unsubscribe(ch)
		ticker := time.NewTicker(ssePingInterval)
		defer ticker.Stop()

		for {
			select {
			case <-r.Context().Done():
				log.Info().
					Str("request_id", chimw.GetReqID(r.Context())).
					Str("session_id", sessionID).
					Err(r.Context().Err()).
					Msg("sse stream closed")
				return
			case ev, ok := <-ch:
				if !ok {
					log.Info().
						Str("request_id", chimw.GetReqID(r.Context())).
						Str("session_id", sessionID).
						Msg("sse stream channel closed")
					return
				}
				if err := agentgateway.WriteSSE(w, ev); err != nil {
					return
				}
				logSSEEvent(r, sessionID, "live", ev)
				_ = coord.Store().UpsertAgentEventOffset(r.Context(), sessionID, ev.EventID)
				flusher.Flush()
			case <-ticker.C:
				ping := agentgateway.StreamEvent{
					EventID:   "",
					Event:     "ping",
					SessionID: sessionID,
					ServerTS:  time.Now().UnixMilli(),
					Data:      map[string]any{"ts": time.Now().UnixMilli()},
				}
				if err := agentgateway.WriteSSE(w, ping); err != nil {
					return
				}
				logSSEEvent(r, sessionID, "ping", ping)
				flusher.Flush()
			}
		}
	}
}

func logSSEEvent(r *http.Request, sessionID, source string, ev agentgateway.StreamEvent) {
	evt := log.Info()
	if ev.Event == "ping" {
		evt = log.Debug()
	}
	evt.
		Str("request_id", chimw.GetReqID(r.Context())).
		Str("session_id", sessionID).
		Str("event", ev.Event).
		Str("event_id", ev.EventID).
		Str("source", source).
		Int64("server_ts", ev.ServerTS).
		Msg("sse event sent")
}
