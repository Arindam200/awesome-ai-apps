package agentgateway

import (
	"strconv"
	"sync"
	"time"
)

type StreamEvent struct {
	EventID   string `json:"event_id"`
	Event     string `json:"event"`
	SessionID string `json:"session_id"`
	ServerTS  int64  `json:"server_ts"`
	Data      any    `json:"data"`
}

type EventBuffer struct {
	mu       sync.Mutex
	nextID   int64
	max      int
	events   []StreamEvent
	watchers map[chan StreamEvent]struct{}
	closed   bool
}

func NewEventBuffer(max int) *EventBuffer {
	if max <= 0 {
		max = 500
	}
	return &EventBuffer{
		max:      max,
		watchers: map[chan StreamEvent]struct{}{},
	}
}

func (b *EventBuffer) Append(event, sessionID string, data any) StreamEvent {
	b.mu.Lock()
	defer b.mu.Unlock()
	if b.closed {
		return StreamEvent{}
	}
	b.nextID++
	ev := StreamEvent{
		EventID:   strconv.FormatInt(b.nextID, 10),
		Event:     event,
		SessionID: sessionID,
		ServerTS:  time.Now().UnixMilli(),
		Data:      data,
	}
	b.events = append(b.events, ev)
	if len(b.events) > b.max {
		b.events = b.events[len(b.events)-b.max:]
	}
	for ch := range b.watchers {
		select {
		case ch <- ev:
		default:
		}
	}
	return ev
}

func (b *EventBuffer) ReplayAfter(lastEventID string) []StreamEvent {
	b.mu.Lock()
	defer b.mu.Unlock()
	if len(b.events) == 0 {
		return nil
	}
	if lastEventID == "" {
		out := make([]StreamEvent, len(b.events))
		copy(out, b.events)
		return out
	}
	last, err := strconv.ParseInt(lastEventID, 10, 64)
	if err != nil {
		out := make([]StreamEvent, len(b.events))
		copy(out, b.events)
		return out
	}
	out := make([]StreamEvent, 0, len(b.events))
	for _, ev := range b.events {
		id, _ := strconv.ParseInt(ev.EventID, 10, 64)
		if id > last {
			out = append(out, ev)
		}
	}
	return out
}

func (b *EventBuffer) Subscribe() chan StreamEvent {
	ch := make(chan StreamEvent, 32)
	b.mu.Lock()
	defer b.mu.Unlock()
	if b.closed {
		close(ch)
		return ch
	}
	b.watchers[ch] = struct{}{}
	return ch
}

func (b *EventBuffer) Unsubscribe(ch chan StreamEvent) {
	b.mu.Lock()
	defer b.mu.Unlock()
	if _, ok := b.watchers[ch]; ok {
		delete(b.watchers, ch)
		close(ch)
	}
}

func (b *EventBuffer) Close() {
	b.mu.Lock()
	defer b.mu.Unlock()
	if b.closed {
		return
	}
	b.closed = true
	for ch := range b.watchers {
		close(ch)
		delete(b.watchers, ch)
	}
}
