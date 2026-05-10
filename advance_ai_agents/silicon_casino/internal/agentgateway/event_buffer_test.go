package agentgateway

import "testing"

func TestEventBufferOrderAndReplay(t *testing.T) {
	buf := NewEventBuffer(10)
	ev1 := buf.Append("a", "s1", map[string]any{"n": 1})
	ev2 := buf.Append("b", "s1", map[string]any{"n": 2})
	ev3 := buf.Append("c", "s1", map[string]any{"n": 3})

	if ev1.EventID != "1" || ev2.EventID != "2" || ev3.EventID != "3" {
		t.Fatalf("unexpected event ids: %s %s %s", ev1.EventID, ev2.EventID, ev3.EventID)
	}

	replay := buf.ReplayAfter("1")
	if len(replay) != 2 {
		t.Fatalf("expected 2 replay events, got %d", len(replay))
	}
	if replay[0].EventID != "2" || replay[1].EventID != "3" {
		t.Fatalf("unexpected replay order: %+v", replay)
	}
}
