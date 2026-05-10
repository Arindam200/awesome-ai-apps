package viewmodel

import (
	"testing"
	"time"

	"silicon-casino/internal/game"
)

func TestBuildAgentStateVisibilityAndSeatData(t *testing.T) {
	st := &game.TableState{
		HandID:        "hand_1",
		Street:        game.StreetFlop,
		Pot:           900,
		Community:     []game.Card{{Rank: game.Ace, Suit: game.Spades}, {Rank: game.King, Suit: game.Hearts}, {Rank: game.Queen, Suit: game.Diamonds}},
		CurrentActor:  0,
		CurrentBet:    400,
		MinRaise:      200,
		RoundBets:     [2]int64{200, 400},
		ActionTimeout: 5 * time.Second,
		Players: [2]*game.Player{
			{ID: "a1", Seat: 0, Stack: 1000, Hole: []game.Card{{Rank: game.Two, Suit: game.Clubs}, {Rank: game.Three, Suit: game.Clubs}}, LastAction: game.ActionCall},
			{ID: "a2", Seat: 1, Stack: 800, Hole: []game.Card{{Rank: game.Four, Suit: game.Clubs}, {Rank: game.Five, Suit: game.Clubs}}, LastAction: game.ActionRaise},
		},
	}

	view := BuildAgentState(st, 0, "turn_1", false)
	if len(view.MyHoleCards) != 2 {
		t.Fatalf("expected 2 own hole cards, got %d", len(view.MyHoleCards))
	}
	if len(view.CommunityCards) != 3 {
		t.Fatalf("expected 3 community cards, got %d", len(view.CommunityCards))
	}
	if len(view.Seats) != 2 {
		t.Fatalf("expected 2 seats, got %d", len(view.Seats))
	}
	if view.Seats[0].StreetContribution != 200 {
		t.Fatalf("expected seat0 contribution 200, got %d", view.Seats[0].StreetContribution)
	}
	if view.Seats[0].ToCall != 200 {
		t.Fatalf("expected seat0 to_call 200, got %d", view.Seats[0].ToCall)
	}
	if view.Seats[1].ToCall != 0 {
		t.Fatalf("expected seat1 to_call 0, got %d", view.Seats[1].ToCall)
	}
	if len(view.LegalActions) == 0 {
		t.Fatalf("expected legal actions")
	}
	if view.ActionConstraints == nil || view.ActionConstraints.Raise == nil {
		t.Fatalf("expected raise constraints in raised pot state")
	}
	if view.ActionConstraints.Bet != nil {
		t.Fatalf("did not expect bet constraints when current_bet > 0")
	}
	if view.ActionConstraints.Raise.MinTo != 600 || view.ActionConstraints.Raise.MaxTo != 1200 {
		t.Fatalf("unexpected raise constraints: %+v", view.ActionConstraints.Raise)
	}
	for _, seat := range view.Seats {
		if len(seat.HoleCards) > 0 {
			t.Fatalf("agent state should not expose seat hole cards: %+v", seat)
		}
	}
}

func TestBuildAgentStateBetOnlyConstraintsWhenCurrentBetIsZero(t *testing.T) {
	st := &game.TableState{
		HandID:        "hand_2",
		Street:        game.StreetFlop,
		Pot:           200,
		CurrentActor:  1,
		CurrentBet:    0,
		MinRaise:      100,
		RoundBets:     [2]int64{0, 0},
		ActionTimeout: 5 * time.Second,
		Players: [2]*game.Player{
			{ID: "a1", Seat: 0, Stack: 500},
			{ID: "a2", Seat: 1, Stack: 1200},
		},
	}

	view := BuildAgentState(st, 1, "turn_2", false)
	hasBet := false
	hasRaise := false
	for _, a := range view.LegalActions {
		if a == string(game.ActionBet) {
			hasBet = true
		}
		if a == string(game.ActionRaise) {
			hasRaise = true
		}
	}
	if !hasBet {
		t.Fatalf("expected bet in legal_actions: %+v", view.LegalActions)
	}
	if hasRaise {
		t.Fatalf("did not expect raise in legal_actions when current_bet=0: %+v", view.LegalActions)
	}
	if view.ActionConstraints == nil || view.ActionConstraints.Bet == nil {
		t.Fatalf("expected bet constraints")
	}
	if view.ActionConstraints.Bet.Min != 100 || view.ActionConstraints.Bet.Max != 1200 {
		t.Fatalf("unexpected bet constraints: %+v", view.ActionConstraints.Bet)
	}
	if view.ActionConstraints.Raise != nil {
		t.Fatalf("did not expect raise constraints")
	}
}

func TestBuildAgentStateRaiseConstraintRespectsEffectiveStack(t *testing.T) {
	st := &game.TableState{
		HandID:        "hand_3",
		Street:        game.StreetTurn,
		Pot:           900,
		CurrentActor:  0,
		CurrentBet:    400,
		MinRaise:      200,
		RoundBets:     [2]int64{100, 400},
		ActionTimeout: 5 * time.Second,
		Players: [2]*game.Player{
			{ID: "a1", Seat: 0, Stack: 450},
			{ID: "a2", Seat: 1, Stack: 3000},
		},
	}

	view := BuildAgentState(st, 0, "turn_3", false)
	// Since max_to (=550) < min_to (=600), raise should not be legal and constraints should be nil.
	hasRaise := false
	for _, a := range view.LegalActions {
		if a == string(game.ActionRaise) {
			hasRaise = true
		}
	}
	if hasRaise {
		t.Fatalf("raise should not be legal when max_to < min_to: %+v", view.LegalActions)
	}
	if view.ActionConstraints != nil && view.ActionConstraints.Raise != nil {
		t.Fatalf("did not expect raise constraints when max_to < min_to: %+v", view.ActionConstraints.Raise)
	}
}

func TestBuildAgentStateCallNotLegalWhenInsufficientStack(t *testing.T) {
	st := &game.TableState{
		HandID:        "hand_4",
		Street:        game.StreetTurn,
		Pot:           700,
		CurrentActor:  0,
		CurrentBet:    500,
		MinRaise:      100,
		RoundBets:     [2]int64{100, 500},
		ActionTimeout: 5 * time.Second,
		Players: [2]*game.Player{
			{ID: "a1", Seat: 0, Stack: 300},
			{ID: "a2", Seat: 1, Stack: 3000},
		},
	}

	view := BuildAgentState(st, 0, "turn_4", false)
	for _, a := range view.LegalActions {
		if a == string(game.ActionCall) {
			t.Fatalf("call should not be legal when stack is below to_call: %+v", view.LegalActions)
		}
	}
}

func TestBuildPublicStateIncludesSeatHoleCards(t *testing.T) {
	st := &game.TableState{
		HandID:        "hand_pub_1",
		Street:        game.StreetFlop,
		Pot:           1200,
		Community:     []game.Card{{Rank: game.Ace, Suit: game.Spades}},
		CurrentActor:  0,
		CurrentBet:    200,
		RoundBets:     [2]int64{200, 200},
		ActionTimeout: 5 * time.Second,
		Players: [2]*game.Player{
			{ID: "p1", Name: "Alpha", Seat: 0, Stack: 900, Hole: []game.Card{{Rank: game.King, Suit: game.Hearts}, {Rank: game.Queen, Suit: game.Hearts}}},
			{ID: "p2", Name: "Beta", Seat: 1, Stack: 800, Hole: []game.Card{{Rank: game.Ten, Suit: game.Clubs}, {Rank: game.Seven, Suit: game.Diamonds}}},
		},
	}

	view := BuildPublicState(st)
	if len(view.Seats) != 2 {
		t.Fatalf("expected 2 seats, got %d", len(view.Seats))
	}
	for _, seat := range view.Seats {
		if len(seat.HoleCards) != 2 {
			t.Fatalf("public state should include 2 hole cards, got %+v", seat)
		}
		if seat.AgentName == "" {
			t.Fatalf("public state should include agent_name, got %+v", seat)
		}
	}
}
