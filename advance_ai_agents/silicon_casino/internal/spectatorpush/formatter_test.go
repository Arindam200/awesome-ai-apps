package spectatorpush

import (
	"strings"
	"testing"
	"time"
)

func TestFormatMessageActionLog(t *testing.T) {
	seat := 1
	amount := int64(320)
	ev := NormalizedEvent{
		EventType:  "action_log",
		RoomID:     "mid",
		TableID:    "t1",
		HandID:     "h1",
		ActorSeat:  &seat,
		Action:     "raise",
		Amount:     &amount,
		ThoughtLog: strings.Repeat("a", 210),
		ServerTS:   1735689600000,
	}
	msg, ok := FormatMessage(ev)
	if !ok {
		t.Fatal("expected formatter to handle action_log")
	}
	if !strings.Contains(msg.Title, "Action") {
		t.Fatalf("unexpected title: %s", msg.Title)
	}
	if msg.Color != colorAction {
		t.Fatalf("unexpected color: %d", msg.Color)
	}
	if _, err := time.Parse(time.RFC3339, msg.Timestamp); err != nil {
		t.Fatalf("invalid timestamp: %v", err)
	}
	foundThought := false
	for _, f := range msg.Fields {
		if f.Name == "Thought" {
			foundThought = true
			if len(f.Value) != thoughtPreviewLimit {
				t.Fatalf("expected trimmed thought length %d, got %d", thoughtPreviewLimit, len(f.Value))
			}
			if f.Inline {
				t.Fatal("expected thought field to be non-inline")
			}
		}
	}
	if !foundThought {
		t.Fatal("expected thought field")
	}
}

func TestFormatMessageSnapshotNoThought(t *testing.T) {
	ev := NormalizedEvent{
		EventType:   "table_snapshot",
		RoomID:      "room_a",
		TableID:     "table_a",
		Street:      "flop",
		TableStatus: "active",
		ThoughtLog:  "ignored",
	}
	msg, ok := FormatMessage(ev)
	if !ok {
		t.Fatal("expected formatter to handle table_snapshot")
	}
	if msg.Color != colorSnapshot {
		t.Fatalf("unexpected snapshot color: %d", msg.Color)
	}
	if !strings.Contains(msg.Description, "Street=flop") {
		t.Fatalf("unexpected snapshot description: %s", msg.Description)
	}
	for _, f := range msg.Fields {
		if f.Name == "Thought" {
			t.Fatal("did not expect thought field for table_snapshot")
		}
	}
}

func TestFormatMessageTableClosedIncludesReason(t *testing.T) {
	ev := NormalizedEvent{
		EventType:   "table_closed",
		RoomID:      "r",
		TableID:     "t",
		TableStatus: "closed",
		CloseReason: "opponent_disconnected",
	}
	msg, ok := FormatMessage(ev)
	if !ok {
		t.Fatal("expected formatter to handle table_closed")
	}
	if msg.Color != colorCritical {
		t.Fatalf("unexpected critical color: %d", msg.Color)
	}
	foundReason := false
	for _, f := range msg.Fields {
		if f.Name == "Reason" && f.Value == "opponent_disconnected" {
			foundReason = true
		}
	}
	if !foundReason {
		t.Fatal("expected reason field")
	}
}
