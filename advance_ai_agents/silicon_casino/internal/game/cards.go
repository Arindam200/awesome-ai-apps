package game

import (
	"math/rand"
	"time"
)

type Suit int

type Rank int

const (
	Spades Suit = iota
	Hearts
	Diamonds
	Clubs
)

const (
	Two   Rank = 2
	Three Rank = 3
	Four  Rank = 4
	Five  Rank = 5
	Six   Rank = 6
	Seven Rank = 7
	Eight Rank = 8
	Nine  Rank = 9
	Ten   Rank = 10
	Jack  Rank = 11
	Queen Rank = 12
	King  Rank = 13
	Ace   Rank = 14
)

type Card struct {
	Rank Rank
	Suit Suit
}

func (c Card) String() string {
	r := map[Rank]string{
		Two: "2", Three: "3", Four: "4", Five: "5", Six: "6", Seven: "7", Eight: "8", Nine: "9", Ten: "T", Jack: "J", Queen: "Q", King: "K", Ace: "A",
	}[c.Rank]
	s := map[Suit]string{Spades: "s", Hearts: "h", Diamonds: "d", Clubs: "c"}[c.Suit]
	return r + s
}

type Deck struct {
	cards []Card
}

func NewDeck() *Deck {
	cards := make([]Card, 0, 52)
	for s := Spades; s <= Clubs; s++ {
		for r := Two; r <= Ace; r++ {
			cards = append(cards, Card{Rank: r, Suit: s})
		}
	}
	return &Deck{cards: cards}
}

func (d *Deck) Shuffle() {
	rnd := rand.New(rand.NewSource(time.Now().UnixNano()))
	rnd.Shuffle(len(d.cards), func(i, j int) {
		d.cards[i], d.cards[j] = d.cards[j], d.cards[i]
	})
}

func (d *Deck) Deal() Card {
	c := d.cards[0]
	d.cards = d.cards[1:]
	return c
}
