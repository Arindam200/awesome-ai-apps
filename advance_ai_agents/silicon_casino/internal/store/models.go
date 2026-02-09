package store

import "time"

type Agent struct {
	ID         string
	Name       string
	APIKeyHash string
	Status     string
	ClaimCode  string
	CreatedAt  time.Time
}

type Account struct {
	AgentID   string
	BalanceCC int64
	UpdatedAt time.Time
}

type Table struct {
	ID           string
	RoomID       string
	Status       string
	SmallBlindCC int64
	BigBlindCC   int64
	CreatedAt    time.Time
}

type Room struct {
	ID           string    `json:"id"`
	Name         string    `json:"name"`
	MinBuyinCC   int64     `json:"min_buyin_cc"`
	SmallBlindCC int64     `json:"small_blind_cc"`
	BigBlindCC   int64     `json:"big_blind_cc"`
	Status       string    `json:"status"`
	CreatedAt    time.Time `json:"created_at"`
}

type Hand struct {
	ID            string
	TableID       string
	WinnerAgentID string
	PotCC         *int64
	StreetEnd     string
	StartedAt     time.Time
	EndedAt       *time.Time
}

type Action struct {
	ID         string
	HandID     string
	AgentID    string
	ActionType string
	AmountCC   int64
	CreatedAt  time.Time
}

type LedgerEntry struct {
	ID        string
	AgentID   string
	Type      string
	AmountCC  int64
	RefType   string
	RefID     string
	CreatedAt time.Time
}

type LeaderboardEntry struct {
	AgentID string
	Name    string
	NetCC   int64
}

type ProxyCall struct {
	ID               string
	AgentID          string
	PromptTokens     int
	CompletionTokens int
	TotalTokens      int
	Model            string
	Provider         string
	CostCC           int64
	CreatedAt        time.Time
}

type AgentClaim struct {
	ID        string
	AgentID   string
	ClaimCode string
	Status    string
	CreatedAt time.Time
}

type AgentKey struct {
	ID         string
	AgentID    string
	Provider   string
	APIKeyHash string
	Status     string
	CreatedAt  time.Time
}

type ProviderRate struct {
	Provider            string
	PricePer1KTokensUSD float64
	CCPerUSD            float64
	Weight              float64
	UpdatedAt           time.Time
}

type AgentBlacklist struct {
	AgentID   string
	Reason    string
	CreatedAt time.Time
}

type AgentKeyAttempt struct {
	ID        string
	AgentID   string
	Provider  string
	Status    string
	CreatedAt time.Time
}

type AgentSession struct {
	ID        string
	AgentID   string
	RoomID    string
	TableID   string
	SeatID    *int
	JoinMode  string
	Status    string
	ExpiresAt time.Time
	CreatedAt time.Time
	ClosedAt  *time.Time
}

type AgentActionRequest struct {
	ID         string
	SessionID  string
	RequestID  string
	TurnID     string
	Action     string
	AmountCC   *int64
	ThoughtLog string
	Accepted   bool
	Reason     string
	CreatedAt  time.Time
}

type AgentEventOffset struct {
	SessionID   string
	LastEventID string
	UpdatedAt   time.Time
}

type TableReplayEvent struct {
	ID           string
	TableID      string
	HandID       string
	GlobalSeq    int64
	HandSeq      *int32
	EventType    string
	ActorAgentID string
	Payload      []byte
	SchemaVer    int32
	CreatedAt    time.Time
}

type TableReplaySnapshot struct {
	ID          string
	TableID     string
	AtGlobalSeq int64
	StateBlob   []byte
	SchemaVer   int32
	CreatedAt   time.Time
}

type AgentTableHistory struct {
	TableID       string
	RoomID        string
	Status        string
	SmallBlindCC  int64
	BigBlindCC    int64
	CreatedAt     time.Time
	LastHandEnded *time.Time
}
