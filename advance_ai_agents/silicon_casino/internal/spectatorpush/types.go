package spectatorpush

import (
	"context"
	"time"

	"silicon-casino/internal/agentgateway"
)

type PushManager interface {
	Start(ctx context.Context) error
	OnTableStarted(meta agentgateway.TableMeta, buf *agentgateway.EventBuffer)
	OnTableClosed(tableID string)
}

type PushTarget struct {
	Platform       string   `json:"platform"`
	Endpoint       string   `json:"endpoint"`
	Secret         string   `json:"secret"`
	ScopeType      string   `json:"scope_type"`
	ScopeValue     string   `json:"scope_value"`
	EventAllowlist []string `json:"event_allowlist"`
	Enabled        bool     `json:"enabled"`
}

type Config struct {
	Enabled             bool
	ConfigPath          string
	ConfigReload        time.Duration
	Targets             []PushTarget
	Workers             int
	RetryMax            int
	RetryBase           time.Duration
	SnapshotMinInterval time.Duration
	PanelUpdateInterval time.Duration
	PanelRecentActions  int
	FailureThreshold    int
	CircuitOpenDuration time.Duration
	RequestTimeout      time.Duration
	DispatchBuffer      int
}

type NormalizedEvent struct {
	EventID     string
	EventType   string
	ServerTS    int64
	TableID     string
	RoomID      string
	HandID      string
	Street      string
	ActorSeat   *int
	CurrentSeat *int
	Action      string
	Amount      *int64
	Pot         *int64
	ThoughtLog  string
	TableStatus string
	CloseReason string
	Raw         map[string]any
}

type MessageField struct {
	Name   string
	Value  string
	Inline bool
}

type FormattedMessage struct {
	PanelKey    string
	Title       string
	Content     string
	Description string
	Color       int
	Timestamp   string
	Footer      string
	Fields      []MessageField
}

type pushJob struct {
	Target        PushTarget
	Event         NormalizedEvent
	Formatted     FormattedMessage
	Attempt       int
	PanelStateKey string
	PanelTerminal bool
}

func (j pushJob) key() string {
	return targetKey(j.Target)
}

func targetKey(t PushTarget) string {
	return t.Platform + "|" + t.Endpoint + "|" + t.ScopeType + "|" + t.ScopeValue
}
