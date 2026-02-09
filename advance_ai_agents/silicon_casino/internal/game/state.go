package game

import "time"

type ActionType string

const (
	ActionFold  ActionType = "fold"
	ActionCheck ActionType = "check"
	ActionCall  ActionType = "call"
	ActionBet   ActionType = "bet"
	ActionRaise ActionType = "raise"
)

type Player struct {
	ID         string
	Name       string
	Stack      int64
	Hole       []Card
	Folded     bool
	AllIn      bool
	LastAction ActionType
	Seat       int
}

type TableState struct {
	TableID       string
	HandID        string
	Players       [2]*Player
	Community     []Card
	DealerPos     int
	Street        Street
	Pot           int64
	MinRaise      int64
	SmallBlind    int64
	BigBlind      int64
	CurrentBet    int64
	RoundBets     [2]int64
	TotalContrib  [2]int64
	Acted         [2]bool
	ActionTimeout time.Duration
	CurrentActor  int
	LastAggressor int
}

type Street string

const (
	StreetPreFlop Street = "preflop"
	StreetFlop    Street = "flop"
	StreetTurn    Street = "turn"
	StreetRiver   Street = "river"
)

type Snapshot struct {
	Type             string     `json:"type"`
	ProtocolVersion  string     `json:"protocol_version"`
	GameID           string     `json:"game_id"`
	HandID           string     `json:"hand_id"`
	HoleCards        []string   `json:"hole_cards,omitempty"`
	CommunityCards   []string   `json:"community_cards"`
	Pot              int64      `json:"pot"`
	MinRaise         int64      `json:"min_raise"`
	CurrentBet       int64      `json:"current_bet,omitempty"`
	CallAmount       int64      `json:"call_amount,omitempty"`
	MyBalance        int64      `json:"my_balance"`
	Opponents        []Opponent `json:"opponents"`
	ActionTimeoutMS  int64      `json:"action_timeout_ms"`
	Street           string     `json:"street"`
	CurrentActorSeat int        `json:"current_actor_seat"`
	MySeat           int        `json:"my_seat"`
}

type Opponent struct {
	Seat   int    `json:"seat"`
	Name   string `json:"name"`
	Stack  int64  `json:"stack"`
	Action string `json:"action"`
}

func (s *TableState) SnapshotFor(playerIdx int, includeHole bool) Snapshot {
	me := s.Players[playerIdx]
	opp := s.Players[1-playerIdx]
	hole := []string{}
	if includeHole {
		for _, c := range me.Hole {
			hole = append(hole, c.String())
		}
	}
	community := []string{}
	for _, c := range s.Community {
		community = append(community, c.String())
	}
	return Snapshot{
		Type:             "state_update",
		ProtocolVersion:  ProtocolVersion,
		GameID:           s.TableID,
		HandID:           s.HandID,
		HoleCards:        hole,
		CommunityCards:   community,
		Pot:              s.Pot,
		MinRaise:         s.MinRaise,
		CurrentBet:       s.CurrentBet,
		CallAmount:       max64(0, s.CurrentBet-s.RoundBets[playerIdx]),
		MyBalance:        me.Stack,
		Opponents:        []Opponent{{Seat: opp.Seat, Name: opp.Name, Stack: opp.Stack, Action: string(opp.LastAction)}},
		ActionTimeoutMS:  int64(s.ActionTimeout / time.Millisecond),
		Street:           string(s.Street),
		CurrentActorSeat: s.Players[s.CurrentActor].Seat,
		MySeat:           me.Seat,
	}
}

func max64(a, b int64) int64 {
	if a > b {
		return a
	}
	return b
}

const ProtocolVersion = "1.0"
