package spectatorpush

import "testing"

func TestFormatDiscordPanelMessageLayout(t *testing.T) {
	turn := 1
	panel := &discordPanelState{
		key:         "k",
		tableID:     "01KH0QRMXAHQK7P9HY85E1G4XV",
		roomID:      "01KGSFH57N4021FBQMH0CW1XYH",
		handID:      "01KH0QSHWFCJ81KZRJYFPAKB2Y",
		street:      "flop",
		tableState:  "active",
		potCC:       320,
		turnSeat:    &turn,
		lastAction:  "S0 bet 100cc",
		lastThought: "Dry board, c-bet for fold equity.",
		lastTS:      1735689600000,
		recent:      []string{"S1 check", "S0 bet 100cc"},
	}

	msg := formatDiscordPanelMessage(panel)
	if msg.Title == "" || msg.Description == "" {
		t.Fatalf("expected non-empty title/description: %#v", msg)
	}
	if len(msg.Fields) < 6 {
		t.Fatalf("expected richer panel fields, got %d", len(msg.Fields))
	}
	if msg.Fields[0].Name != "🃏 Street" || msg.Fields[1].Name != "💰 Pot" || msg.Fields[2].Name != "🎯 Turn" {
		t.Fatalf("unexpected top layout fields: %#v", msg.Fields[:3])
	}
}
