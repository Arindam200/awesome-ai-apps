package viewmodel

import "silicon-casino/internal/game"

type SeatView struct {
	SeatID             int      `json:"seat_id"`
	AgentID            string   `json:"agent_id"`
	AgentName          string   `json:"agent_name,omitempty"`
	Stack              int64    `json:"stack"`
	StreetContribution int64    `json:"street_contribution"`
	ToCall             int64    `json:"to_call"`
	HoleCards          []string `json:"hole_cards,omitempty"`
	LastAction         string   `json:"last_action"`
	LastActionAmount   *int64   `json:"last_action_amount,omitempty"`
	IsActive           bool     `json:"is_active"`
}

type AgentStateView struct {
	HandID              string             `json:"hand_id"`
	Street              string             `json:"street"`
	Pot                 int64              `json:"pot"`
	CommunityCards      []string           `json:"community_cards"`
	CurrentActorSeat    int                `json:"current_actor_seat"`
	TurnID              string             `json:"turn_id"`
	ActionTimeoutMS     int64              `json:"action_timeout_ms"`
	MySeat              int                `json:"my_seat"`
	MyBalance           int64              `json:"my_balance"`
	MyHoleCards         []string           `json:"my_hole_cards"`
	LegalActions        []string           `json:"legal_actions,omitempty"`
	ActionConstraints   *ActionConstraints `json:"action_constraints,omitempty"`
	Seats               []SeatView         `json:"seats"`
	TableStatus         string             `json:"table_status,omitempty"`
	ReconnectDeadlineTS int64              `json:"reconnect_deadline_ts,omitempty"`
	CloseReason         string             `json:"close_reason,omitempty"`
}

type BetConstraint struct {
	Min int64 `json:"min"`
	Max int64 `json:"max"`
}

type RaiseConstraint struct {
	MinTo int64 `json:"min_to"`
	MaxTo int64 `json:"max_to"`
}

type ActionConstraints struct {
	Bet   *BetConstraint   `json:"bet,omitempty"`
	Raise *RaiseConstraint `json:"raise,omitempty"`
}

type PublicStateView struct {
	HandID              string     `json:"hand_id"`
	Street              string     `json:"street"`
	Pot                 int64      `json:"pot"`
	CommunityCards      []string   `json:"community_cards"`
	CurrentActorSeat    int        `json:"current_actor_seat"`
	ActionTimeoutMS     int64      `json:"action_timeout_ms"`
	Seats               []SeatView `json:"seats"`
	TableStatus         string     `json:"table_status,omitempty"`
	ReconnectDeadlineTS int64      `json:"reconnect_deadline_ts,omitempty"`
	CloseReason         string     `json:"close_reason,omitempty"`
}

func BuildAgentState(st *game.TableState, mySeat int, turnID string, includeOthersHole bool) AgentStateView {
	community := make([]string, 0, len(st.Community))
	for _, c := range st.Community {
		community = append(community, c.String())
	}

	myCards := []string{}
	for _, c := range st.Players[mySeat].Hole {
		myCards = append(myCards, c.String())
	}

	seats := make([]SeatView, 0, len(st.Players))
	for i, p := range st.Players {
		if p == nil {
			continue
		}
		toCall := st.CurrentBet - st.RoundBets[i]
		if toCall < 0 {
			toCall = 0
		}
		var lastAmount *int64
		if st.RoundBets[i] > 0 {
			v := st.RoundBets[i]
			lastAmount = &v
		}
		seats = append(seats, SeatView{
			SeatID:             p.Seat,
			AgentID:            p.ID,
			AgentName:          p.Name,
			Stack:              p.Stack,
			StreetContribution: st.RoundBets[i],
			ToCall:             toCall,
			LastAction:         string(p.LastAction),
			LastActionAmount:   lastAmount,
			IsActive:           !p.Folded,
		})
	}

	myBalance := int64(0)
	if st.Players[mySeat] != nil {
		myBalance = st.Players[mySeat].Stack
	}
	legalActions, actionConstraints := buildLegalActionsAndConstraints(st, mySeat)
	out := AgentStateView{
		HandID:            st.HandID,
		Street:            string(st.Street),
		Pot:               st.Pot,
		CommunityCards:    community,
		CurrentActorSeat:  st.Players[st.CurrentActor].Seat,
		TurnID:            turnID,
		ActionTimeoutMS:   int64(st.ActionTimeout.Milliseconds()),
		MySeat:            mySeat,
		MyBalance:         myBalance,
		MyHoleCards:       myCards,
		LegalActions:      legalActions,
		ActionConstraints: actionConstraints,
		Seats:             seats,
	}
	if includeOthersHole {
		// Intentionally no-op here for now; showdown payload handles full reveal.
	}
	return out
}

func buildLegalActionsAndConstraints(st *game.TableState, mySeat int) ([]string, *ActionConstraints) {
	if mySeat < 0 || mySeat >= len(st.Players) || st.Players[mySeat] == nil {
		return nil, nil
	}
	me := st.Players[mySeat]
	if me.Folded || st.CurrentActor != mySeat {
		return nil, nil
	}

	legal := make([]string, 0, 5)
	constraints := &ActionConstraints{}
	legal = append(legal, string(game.ActionFold))

	if st.CurrentBet == st.RoundBets[mySeat] {
		legal = append(legal, string(game.ActionCheck))
	}
	if st.CurrentBet > st.RoundBets[mySeat] {
		toCall := st.CurrentBet - st.RoundBets[mySeat]
		if toCall > 0 && me.Stack >= toCall {
			legal = append(legal, string(game.ActionCall))
		}
	}
	if st.CurrentBet == 0 {
		maxBet := me.Stack
		if maxBet >= st.MinRaise {
			legal = append(legal, string(game.ActionBet))
			constraints.Bet = &BetConstraint{
				Min: st.MinRaise,
				Max: maxBet,
			}
		}
	}
	if st.CurrentBet > 0 {
		minTo := st.CurrentBet + st.MinRaise
		maxTo := st.RoundBets[mySeat] + me.Stack
		if maxTo >= minTo {
			legal = append(legal, string(game.ActionRaise))
			constraints.Raise = &RaiseConstraint{
				MinTo: minTo,
				MaxTo: maxTo,
			}
		}
	}
	if constraints.Bet == nil && constraints.Raise == nil {
		return legal, nil
	}
	return legal, constraints
}

func BuildPublicState(st *game.TableState) PublicStateView {
	community := make([]string, 0, len(st.Community))
	for _, c := range st.Community {
		community = append(community, c.String())
	}

	seats := make([]SeatView, 0, len(st.Players))
	for i, p := range st.Players {
		if p == nil {
			continue
		}
		toCall := st.CurrentBet - st.RoundBets[i]
		if toCall < 0 {
			toCall = 0
		}
		var lastAmount *int64
		if st.RoundBets[i] > 0 {
			v := st.RoundBets[i]
			lastAmount = &v
		}
		holeCards := make([]string, 0, len(p.Hole))
		for _, c := range p.Hole {
			holeCards = append(holeCards, c.String())
		}
		seats = append(seats, SeatView{
			SeatID:             p.Seat,
			AgentID:            p.ID,
			AgentName:          p.Name,
			Stack:              p.Stack,
			StreetContribution: st.RoundBets[i],
			ToCall:             toCall,
			HoleCards:          holeCards,
			LastAction:         string(p.LastAction),
			LastActionAmount:   lastAmount,
			IsActive:           !p.Folded,
		})
	}
	return PublicStateView{
		HandID:           st.HandID,
		Street:           string(st.Street),
		Pot:              st.Pot,
		CommunityCards:   community,
		CurrentActorSeat: st.Players[st.CurrentActor].Seat,
		ActionTimeoutMS:  int64(st.ActionTimeout.Milliseconds()),
		Seats:            seats,
	}
}
