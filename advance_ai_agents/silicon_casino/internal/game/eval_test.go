package game

import "testing"

func TestEvaluate7StraightFlush(t *testing.T) {
	cards := []Card{{Ace, Spades}, {King, Spades}, {Queen, Spades}, {Jack, Spades}, {Ten, Spades}, {Two, Hearts}, {Three, Clubs}}
	r := Evaluate7(cards)
	if r.Category != 8 {
		t.Fatalf("expected straight flush, got %d", r.Category)
	}
}

func TestEvaluate7FullHouse(t *testing.T) {
	cards := []Card{{Ace, Spades}, {Ace, Hearts}, {Ace, Clubs}, {King, Spades}, {King, Diamonds}, {Two, Hearts}, {Three, Clubs}}
	r := Evaluate7(cards)
	if r.Category != 6 {
		t.Fatalf("expected full house, got %d", r.Category)
	}
}

func TestEvaluate7TwoPair(t *testing.T) {
	cards := []Card{{Ace, Spades}, {Ace, Hearts}, {King, Clubs}, {King, Diamonds}, {Two, Hearts}, {Three, Clubs}, {Four, Spades}}
	r := Evaluate7(cards)
	if r.Category != 2 {
		t.Fatalf("expected two pair, got %d", r.Category)
	}
}
