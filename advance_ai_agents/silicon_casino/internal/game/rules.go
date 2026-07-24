package game

import "errors"

var ErrInvalidAction = errors.New("invalid_action")
var ErrNotYourTurn = errors.New("not_your_turn")

func ValidateAction(s *TableState, playerIdx int, action ActionType, amount int64) error {
	if playerIdx != s.CurrentActor {
		return ErrNotYourTurn
	}
	me := s.Players[playerIdx]
	if me.Folded {
		return ErrInvalidAction
	}
	switch action {
	case ActionFold:
		return nil
	case ActionCheck:
		if s.CurrentBet != s.RoundBets[playerIdx] {
			return ErrInvalidAction
		}
		return nil
	case ActionCall:
		if s.CurrentBet <= s.RoundBets[playerIdx] {
			return ErrInvalidAction
		}
		return nil
	case ActionBet:
		if s.CurrentBet != 0 {
			return ErrInvalidAction
		}
		if amount < s.MinRaise {
			return ErrInvalidAction
		}
		return nil
	case ActionRaise:
		if s.CurrentBet == 0 {
			return ErrInvalidAction
		}
		if amount < s.CurrentBet+s.MinRaise {
			return ErrInvalidAction
		}
		return nil
	default:
		return ErrInvalidAction
	}
}
