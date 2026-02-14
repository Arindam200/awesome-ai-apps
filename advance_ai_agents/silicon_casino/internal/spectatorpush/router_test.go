package spectatorpush

import "testing"

func TestRouterMatchTargets(t *testing.T) {
	r := Router{}
	targets := []PushTarget{
		{Platform: "discord", Endpoint: "https://x/1", ScopeType: "room", ScopeValue: "room_a", Enabled: true},
		{Platform: "feishu", Endpoint: "https://x/2", ScopeType: "table", ScopeValue: "table_x", Enabled: true},
		{Platform: "discord", Endpoint: "https://x/3", ScopeType: "all", Enabled: true, EventAllowlist: []string{"table_closed"}},
	}
	ev := NormalizedEvent{EventType: "action_log", RoomID: "room_a", TableID: "table_x"}
	matched := r.MatchTargets(targets, ev)
	if len(matched) != 2 {
		t.Fatalf("expected 2 targets, got %d", len(matched))
	}

	evClose := NormalizedEvent{EventType: "table_closed", RoomID: "room_a", TableID: "table_x"}
	matchedClose := r.MatchTargets(targets, evClose)
	if len(matchedClose) != 3 {
		t.Fatalf("expected 3 targets, got %d", len(matchedClose))
	}
}
