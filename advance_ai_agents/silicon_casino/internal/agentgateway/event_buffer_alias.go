package agentgateway

import agstream "silicon-casino/internal/agentgateway/stream"

type StreamEvent = agstream.StreamEvent
type EventBuffer = agstream.EventBuffer

func NewEventBuffer(max int) *EventBuffer {
	return agstream.NewEventBuffer(max)
}
