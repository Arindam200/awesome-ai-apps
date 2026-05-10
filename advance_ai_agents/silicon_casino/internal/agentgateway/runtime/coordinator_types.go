package runtime

import (
	"sync"
	"time"

	"silicon-casino/internal/game"
	"silicon-casino/internal/ledger"
	"silicon-casino/internal/store"
)

const (
	sessionTTL               = 2 * time.Hour
	tableStatusActive        = "active"
	tableStatusClosing       = "closing"
	tableStatusClosed        = "closed"
	defaultReconnectGrace    = 30 * time.Second
	coordinatorSweepInterval = 500 * time.Millisecond
)

var reconnectGracePeriod = defaultReconnectGrace

type sessionState struct {
	session            store.AgentSession
	agent              *store.Agent
	runtime            *tableRuntime
	seat               int
	buffer             *EventBuffer
	disconnected       bool
	disconnectedReason string
}

type Coordinator struct {
	store  *store.Store
	ledger *ledger.Ledger

	mu            sync.Mutex
	waiting       map[string]*sessionState
	sessions      map[string]*sessionState
	byAgent       map[string]*sessionState
	tables        map[string]*tableRuntime
	tableObserver TableLifecycleObserver
}

func NewCoordinator(st *store.Store, led *ledger.Ledger) *Coordinator {
	return &Coordinator{
		store:    st,
		ledger:   led,
		waiting:  map[string]*sessionState{},
		sessions: map[string]*sessionState{},
		byAgent:  map[string]*sessionState{},
		tables:   map[string]*tableRuntime{},
	}
}

type tableRuntime struct {
	id                  string
	room                *store.Room
	engine              *game.Engine
	players             [2]*sessionState
	turnID              string
	globalSeq           int64
	handSeq             int32
	eventsSinceSnapshot int
	snapshotInterval    int32
	replayClosed        bool
	publicBuffer        *EventBuffer
	status              string
	closeReason         string
	reconnectDeadline   time.Time
	disconnectedSeat    int
	turnDeadline        time.Time
	turnSeat            int
	mu                  sync.Mutex
}

func nextTurnID() string {
	return "turn_" + store.NewID()
}
