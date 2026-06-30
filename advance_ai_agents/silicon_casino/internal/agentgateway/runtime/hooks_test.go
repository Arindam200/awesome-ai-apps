package runtime

import (
	"context"
	"testing"
	"time"

	"silicon-casino/internal/ledger"
	"silicon-casino/internal/testutil"
)

type recordingObserver struct {
	started chan TableMeta
	closed  chan string
}

func (o *recordingObserver) OnTableStarted(meta TableMeta, _ *EventBuffer) {
	select {
	case o.started <- meta:
	default:
	}
}

func (o *recordingObserver) OnTableClosed(tableID string) {
	select {
	case o.closed <- tableID:
	default:
	}
}

func TestTableLifecycleObserverStartAndClose(t *testing.T) {
	st, cleanup := testutil.OpenTestStore(t)
	defer cleanup()
	ctx := context.Background()
	if err := st.EnsureDefaultRooms(ctx); err != nil {
		t.Fatalf("ensure rooms: %v", err)
	}
	a1, _ := st.CreateAgent(ctx, "obs-a", "obs-key-a", "obs-claim-a")
	a2, _ := st.CreateAgent(ctx, "obs-b", "obs-key-b", "obs-claim-b")
	_ = st.EnsureAccount(ctx, a1, 100000)
	_ = st.EnsureAccount(ctx, a2, 100000)

	coord := NewCoordinator(st, ledger.New(st))
	observer := &recordingObserver{started: make(chan TableMeta, 1), closed: make(chan string, 1)}
	coord.SetTableLifecycleObserver(observer)

	if _, err := coord.CreateSession(ctx, CreateSessionRequest{AgentID: a1, APIKey: "obs-key-a", JoinMode: "random"}); err != nil {
		t.Fatalf("create first session: %v", err)
	}
	s2, err := coord.CreateSession(ctx, CreateSessionRequest{AgentID: a2, APIKey: "obs-key-b", JoinMode: "random"})
	if err != nil {
		t.Fatalf("create second session: %v", err)
	}
	if s2.TableID == "" {
		t.Fatal("expected table id")
	}

	select {
	case meta := <-observer.started:
		if meta.TableID != s2.TableID {
			t.Fatalf("unexpected table id: %s", meta.TableID)
		}
		if meta.RoomID == "" {
			t.Fatal("expected room id")
		}
	case <-time.After(time.Second):
		t.Fatal("timeout waiting observer start callback")
	}

	prev := reconnectGracePeriod
	reconnectGracePeriod = 20 * time.Millisecond
	defer func() { reconnectGracePeriod = prev }()

	if err := coord.CloseSessionWithReason(ctx, s2.SessionID, "client_closed"); err != nil {
		t.Fatalf("close session: %v", err)
	}
	time.Sleep(30 * time.Millisecond)
	coord.sweepTableTransitions(ctx, time.Now())

	select {
	case tableID := <-observer.closed:
		if tableID != s2.TableID {
			t.Fatalf("unexpected close table id: %s", tableID)
		}
	case <-time.After(time.Second):
		t.Fatal("timeout waiting observer close callback")
	}
}
