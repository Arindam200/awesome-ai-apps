package game

import (
	"context"
	"errors"
	"time"

	"silicon-casino/internal/ledger"
	"silicon-casino/internal/store"
)

type Engine struct {
	Store  *store.Store
	Ledger *ledger.Ledger
	State  *TableState
	Deck   *Deck
}

func NewEngine(store *store.Store, ledger *ledger.Ledger, tableID string, sb, bb int64) *Engine {
	state := &TableState{
		TableID:       tableID,
		SmallBlind:    sb,
		BigBlind:      bb,
		MinRaise:      bb,
		ActionTimeout: 30 * time.Second,
		DealerPos:     0,
	}
	return &Engine{Store: store, Ledger: ledger, State: state}
}

func (e *Engine) StartHand(ctx context.Context, p1, p2 *Player, sb, bb int64) error {
	e.State.Players[0] = p1
	e.State.Players[1] = p2
	e.State.HandID = ""
	e.State.Community = nil
	e.State.Street = StreetPreFlop
	e.State.Pot = 0
	e.State.CurrentBet = 0
	e.State.RoundBets = [2]int64{}
	e.State.TotalContrib = [2]int64{}
	e.State.Acted = [2]bool{}

	e.State.DealerPos = 1 - e.State.DealerPos
	e.State.SmallBlind = sb
	e.State.BigBlind = bb
	e.State.MinRaise = bb

	handID, err := e.Store.CreateHand(ctx, e.State.TableID)
	if err != nil {
		return err
	}
	e.State.HandID = handID

	e.Deck = NewDeck()
	e.Deck.Shuffle()
	for i := 0; i < 2; i++ {
		p := e.State.Players[i]
		p.Folded = false
		p.AllIn = false
		p.LastAction = ""
		p.Hole = []Card{e.Deck.Deal(), e.Deck.Deal()}
	}

	// Load balances
	for i := 0; i < 2; i++ {
		bal, err := e.Store.GetAccountBalance(ctx, e.State.Players[i].ID)
		if err != nil {
			return err
		}
		e.State.Players[i].Stack = bal
	}

	// Brain dead rule
	for i := 0; i < 2; i++ {
		if e.State.Players[i].Stack < bb {
			e.State.Players[i].Folded = true
		}
	}

	// Post blinds if not folded
	sbIdx := e.State.DealerPos
	bbIdx := 1 - sbIdx
	if !e.State.Players[sbIdx].Folded {
		newBal, err := e.Ledger.DebitBlind(ctx, e.State.Players[sbIdx].ID, handID, sb)
		if err != nil {
			return err
		}
		e.State.Players[sbIdx].Stack = newBal
		e.State.RoundBets[sbIdx] = sb
		e.State.TotalContrib[sbIdx] = sb
	}
	if !e.State.Players[bbIdx].Folded {
		newBal, err := e.Ledger.DebitBlind(ctx, e.State.Players[bbIdx].ID, handID, bb)
		if err != nil {
			return err
		}
		e.State.Players[bbIdx].Stack = newBal
		e.State.RoundBets[bbIdx] = bb
		e.State.TotalContrib[bbIdx] = bb
		e.State.CurrentBet = bb
	}
	e.State.Pot = e.State.RoundBets[0] + e.State.RoundBets[1]

	// Preflop: small blind acts first
	e.State.CurrentActor = sbIdx
	return nil
}

type Action struct {
	Player int
	Type   ActionType
	Amount int64
}

func (e *Engine) ApplyAction(ctx context.Context, a Action) (bool, error) {
	s := e.State
	if err := ValidateAction(s, a.Player, a.Type, a.Amount); err != nil {
		return false, err
	}
	p := s.Players[a.Player]
	oppIdx := 1 - a.Player
	paid := int64(0)

	s.Acted[a.Player] = true
	p.LastAction = a.Type

	switch a.Type {
	case ActionFold:
		p.Folded = true
		return true, nil
	case ActionCheck:
		// no chips
	case ActionCall:
		need := s.CurrentBet - s.RoundBets[a.Player]
		if need < 0 {
			need = 0
		}
		if need > 0 {
			if err := e.debitBet(ctx, a.Player, need); err != nil {
				return false, err
			}
			s.RoundBets[a.Player] += need
			s.TotalContrib[a.Player] += need
			s.Pot += need
			paid = need
		}
	case ActionBet:
		amount := a.Amount
		if err := e.debitBet(ctx, a.Player, amount); err != nil {
			return false, err
		}
		s.RoundBets[a.Player] += amount
		s.TotalContrib[a.Player] += amount
		s.CurrentBet = s.RoundBets[a.Player]
		s.MinRaise = amount
		s.Pot += amount
		s.LastAggressor = a.Player
		paid = amount
	case ActionRaise:
		to := a.Amount
		need := to - s.RoundBets[a.Player]
		if need < 0 {
			return false, errors.New("invalid_raise")
		}
		if err := e.debitBet(ctx, a.Player, need); err != nil {
			return false, err
		}
		prevBet := s.CurrentBet
		s.RoundBets[a.Player] = to
		s.TotalContrib[a.Player] += need
		s.CurrentBet = to
		s.MinRaise = to - prevBet
		s.Pot += need
		s.LastAggressor = a.Player
		paid = need
	}

	if e.Store != nil {
		_ = e.Store.RecordAction(ctx, s.HandID, p.ID, string(a.Type), paid)
	}

	if p.Stack == 0 {
		p.AllIn = true
	}

	if s.Players[oppIdx].Folded {
		return true, nil
	}

	if s.RoundBets[0] == s.RoundBets[1] && s.Acted[0] && s.Acted[1] {
		return true, nil
	}

	s.CurrentActor = oppIdx
	return false, nil
}

func (e *Engine) NextStreet() {
	s := e.State
	s.RoundBets = [2]int64{}
	s.Acted = [2]bool{}
	s.CurrentBet = 0
	s.MinRaise = s.BigBlind

	switch s.Street {
	case StreetPreFlop:
		s.Community = append(s.Community, e.Deck.Deal(), e.Deck.Deal(), e.Deck.Deal())
		s.Street = StreetFlop
	case StreetFlop:
		s.Community = append(s.Community, e.Deck.Deal())
		s.Street = StreetTurn
	case StreetTurn:
		s.Community = append(s.Community, e.Deck.Deal())
		s.Street = StreetRiver
	}
	// postflop: big blind acts first (i.e. non-dealer)
	s.CurrentActor = 1 - s.DealerPos
}

func (e *Engine) FastForwardToShowdown() {
	s := e.State
	for s.Street != StreetRiver {
		e.NextStreet()
	}
}

func (e *Engine) Settle(ctx context.Context) (string, error) {
	s := e.State
	p0 := s.Players[0]
	p1 := s.Players[1]

	var winner string
	if p0.Folded && !p1.Folded {
		winner = p1.ID
	} else if p1.Folded && !p0.Folded {
		winner = p0.ID
	} else {
		cards0 := append([]Card{}, p0.Hole...)
		cards0 = append(cards0, s.Community...)
		cards1 := append([]Card{}, p1.Hole...)
		cards1 = append(cards1, s.Community...)
		r0 := Evaluate7(cards0)
		r1 := Evaluate7(cards1)
		if r0.BetterThan(r1) {
			winner = p0.ID
		} else if r1.BetterThan(r0) {
			winner = p1.ID
		} else {
			winner = "split"
		}
	}

	pot := ComputePot(s.TotalContrib[0], s.TotalContrib[1])
	if winner == "split" {
		// split main pot only
		half := pot.Main / 2
		if bal, err := e.Ledger.CreditPot(ctx, p0.ID, s.HandID, half); err == nil {
			p0.Stack = bal
		}
		if bal, err := e.Ledger.CreditPot(ctx, p1.ID, s.HandID, pot.Main-half); err == nil {
			p1.Stack = bal
		}
		if pot.HasSide {
			// side pot to bigger stack (contributor)
			if s.TotalContrib[0] > s.TotalContrib[1] {
				if bal, err := e.Ledger.CreditPot(ctx, p0.ID, s.HandID, pot.Side); err == nil {
					p0.Stack = bal
				}
			} else {
				if bal, err := e.Ledger.CreditPot(ctx, p1.ID, s.HandID, pot.Side); err == nil {
					p1.Stack = bal
				}
			}
		}
		return "split", nil
	}

	if winner == p0.ID {
		if bal, err := e.Ledger.CreditPot(ctx, p0.ID, s.HandID, pot.Main); err == nil {
			p0.Stack = bal
		}
		if pot.HasSide && s.TotalContrib[0] > s.TotalContrib[1] {
			if bal, err := e.Ledger.CreditPot(ctx, p0.ID, s.HandID, pot.Side); err == nil {
				p0.Stack = bal
			}
		} else if pot.HasSide {
			if bal, err := e.Ledger.CreditPot(ctx, p1.ID, s.HandID, pot.Side); err == nil {
				p1.Stack = bal
			}
		}
		return p0.ID, nil
	}
	if bal, err := e.Ledger.CreditPot(ctx, p1.ID, s.HandID, pot.Main); err == nil {
		p1.Stack = bal
	}
	if pot.HasSide && s.TotalContrib[1] > s.TotalContrib[0] {
		if bal, err := e.Ledger.CreditPot(ctx, p1.ID, s.HandID, pot.Side); err == nil {
			p1.Stack = bal
		}
	} else if pot.HasSide {
		if bal, err := e.Ledger.CreditPot(ctx, p0.ID, s.HandID, pot.Side); err == nil {
			p0.Stack = bal
		}
	}
	return p1.ID, nil
}

func (e *Engine) debitBet(ctx context.Context, playerIdx int, amount int64) error {
	if amount <= 0 {
		return nil
	}
	p := e.State.Players[playerIdx]
	if e.Store == nil {
		if p.Stack < amount {
			return errors.New("insufficient_balance")
		}
		p.Stack -= amount
	} else {
		newBal, err := e.Store.Debit(ctx, p.ID, amount, "bet_debit", "hand", e.State.HandID)
		if err != nil {
			return err
		}
		p.Stack = newBal
	}
	if p.Stack < 0 {
		return errors.New("negative_stack")
	}
	return nil
}
