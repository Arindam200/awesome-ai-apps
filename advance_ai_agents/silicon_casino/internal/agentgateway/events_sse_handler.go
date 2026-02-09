package agentgateway

import (
	"encoding/json"
	"fmt"
	"net/http"
	"time"

	"github.com/go-chi/chi/v5"
	chimw "github.com/go-chi/chi/v5/middleware"
	"github.com/rs/zerolog/log"
)

var ssePingInterval = 15 * time.Second

func EventsSSEHandler(coord *Coordinator) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		sessionID := chi.URLParam(r, "session_id")
		if sessionID == "" {
			writeErr(w, http.StatusBadRequest, "session_not_found")
			return
		}
		buf := coord.getSessionBuffer(sessionID)
		if buf == nil {
			writeErr(w, http.StatusNotFound, "session_not_found")
			return
		}
		flusher, ok := w.(http.Flusher)
		if !ok {
			writeErr(w, http.StatusInternalServerError, "stream_not_supported")
			return
		}

		metricAgentSSEConnectionsTotal.Add(1)
		metricAgentSSEConnectionsActive.Add(1)
		defer metricAgentSSEConnectionsActive.Add(-1)

		SetSSEHeaders(w)
		log.Info().
			Str("request_id", chimw.GetReqID(r.Context())).
			Str("session_id", sessionID).
			Msg("sse stream opened")

		lastEventID := r.Header.Get("Last-Event-ID")
		if lastEventID == "" {
			if off, err := coord.store.GetAgentEventOffset(r.Context(), sessionID); err == nil && off.LastEventID != "" {
				lastEventID = off.LastEventID
			}
		}
		replay := buf.ReplayAfter(lastEventID)
		for _, ev := range replay {
			if err := WriteSSE(w, ev); err != nil {
				return
			}
			logSSEEvent(r, sessionID, "replay", ev)
			_ = coord.store.UpsertAgentEventOffset(r.Context(), sessionID, ev.EventID)
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
				if err := WriteSSE(w, ev); err != nil {
					return
				}
				logSSEEvent(r, sessionID, "live", ev)
				_ = coord.store.UpsertAgentEventOffset(r.Context(), sessionID, ev.EventID)
				flusher.Flush()
			case <-ticker.C:
				ping := StreamEvent{
					EventID:   "",
					Event:     "ping",
					SessionID: sessionID,
					ServerTS:  time.Now().UnixMilli(),
					Data:      map[string]any{"ts": time.Now().UnixMilli()},
				}
				if err := WriteSSE(w, ping); err != nil {
					return
				}
				logSSEEvent(r, sessionID, "ping", ping)
				flusher.Flush()
			}
		}
	}
}

func (c *Coordinator) getSessionBuffer(sessionID string) *EventBuffer {
	c.mu.Lock()
	defer c.mu.Unlock()
	sess := c.sessions[sessionID]
	if sess == nil {
		return nil
	}
	return sess.buffer
}

func WriteSSE(w http.ResponseWriter, ev StreamEvent) error {
	data, err := json.Marshal(ev)
	if err != nil {
		return err
	}
	if ev.EventID != "" {
		if _, err := fmt.Fprintf(w, "id: %s\n", ev.EventID); err != nil {
			return err
		}
	}
	if _, err := fmt.Fprintf(w, "event: %s\n", ev.Event); err != nil {
		return err
	}
	if _, err := fmt.Fprintf(w, "data: %s\n\n", data); err != nil {
		return err
	}
	return nil
}

func logSSEEvent(r *http.Request, sessionID, source string, ev StreamEvent) {
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
