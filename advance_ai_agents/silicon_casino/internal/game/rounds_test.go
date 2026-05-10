package game

import "testing"

func TestRoundCheckCheckCompletes(t *testing.T) {
	e := &Engine{State: &TableState{MinRaise: 200, BigBlind: 200}}
	e.State.Players[0] = &Player{ID: "p0", Stack: 1000}
	e.State.Players[1] = &Player{ID: "p1", Stack: 1000}
	e.State.CurrentActor = 0

	done, err := e.ApplyAction(nil, Action{Player: 0, Type: ActionCheck})
	if err != nil || done {
		t.Fatalf("expected not done after first check, err=%v done=%v", err, done)
	}
	e.State.CurrentActor = 1
	done, err = e.ApplyAction(nil, Action{Player: 1, Type: ActionCheck})
	if err != nil || !done {
		t.Fatalf("expected done after check/check, err=%v done=%v", err, done)
	}
}

func TestRoundBetCallCompletes(t *testing.T) {
	e := &Engine{State: &TableState{MinRaise: 200, BigBlind: 200}}
	e.State.Players[0] = &Player{ID: "p0", Stack: 1000}
	e.State.Players[1] = &Player{ID: "p1", Stack: 1000}
	e.State.CurrentActor = 0

	done, err := e.ApplyAction(nil, Action{Player: 0, Type: ActionBet, Amount: 200})
	if err != nil || done {
		t.Fatalf("expected not done after bet, err=%v done=%v", err, done)
	}
	e.State.CurrentActor = 1
	done, err = e.ApplyAction(nil, Action{Player: 1, Type: ActionCall})
	if err != nil || !done {
		t.Fatalf("expected done after bet/call, err=%v done=%v", err, done)
	}
}

func TestRoundRaiseRaiseCallCompletes(t *testing.T) {
	e := &Engine{State: &TableState{MinRaise: 200, BigBlind: 200, CurrentBet: 200}}
	e.State.Players[0] = &Player{ID: "p0", Stack: 2000}
	e.State.Players[1] = &Player{ID: "p1", Stack: 2000}
	e.State.RoundBets[0] = 200
	e.State.RoundBets[1] = 0
	e.State.CurrentActor = 1

	done, err := e.ApplyAction(nil, Action{Player: 1, Type: ActionRaise, Amount: 400})
	if err != nil || done {
		t.Fatalf("expected not done after raise, err=%v done=%v", err, done)
	}
	e.State.CurrentActor = 0
	done, err = e.ApplyAction(nil, Action{Player: 0, Type: ActionRaise, Amount: 600})
	if err != nil || done {
		t.Fatalf("expected not done after re-raise, err=%v done=%v", err, done)
	}
	e.State.CurrentActor = 1
	done, err = e.ApplyAction(nil, Action{Player: 1, Type: ActionCall})
	if err != nil || !done {
		t.Fatalf("expected done after raise/raise/call, err=%v done=%v", err, done)
	}
}
