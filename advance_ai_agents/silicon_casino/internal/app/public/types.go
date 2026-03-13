package public

import "time"

type RoomsResponse struct {
	Items []RoomItem `json:"items"`
}

type RoomItem struct {
	ID           string `json:"id"`
	Name         string `json:"name"`
	MinBuyinCC   int64  `json:"min_buyin_cc"`
	SmallBlindCC int64  `json:"small_blind_cc"`
	BigBlindCC   int64  `json:"big_blind_cc"`
}

type TablesResponse struct {
	Items  []TableItem `json:"items"`
	Limit  int         `json:"limit"`
	Offset int         `json:"offset"`
}

type TableItem struct {
	TableID      string    `json:"table_id"`
	RoomID       string    `json:"room_id"`
	Status       string    `json:"status"`
	CreatedAt    time.Time `json:"created_at"`
	SmallBlindCC int64     `json:"small_blind_cc"`
	BigBlindCC   int64     `json:"big_blind_cc"`
}

type TableHistoryResponse struct {
	Items  []TableHistoryItem `json:"items"`
	Total  int                `json:"total"`
	Limit  int                `json:"limit"`
	Offset int                `json:"offset"`
}

type TableHistoryItem struct {
	TableID       string                    `json:"table_id"`
	RoomID        string                    `json:"room_id"`
	RoomName      string                    `json:"room_name"`
	Status        string                    `json:"status"`
	SmallBlindCC  int64                     `json:"small_blind_cc"`
	BigBlindCC    int64                     `json:"big_blind_cc"`
	HandsPlayed   int                       `json:"hands_played"`
	Participants  []TableHistoryParticipant `json:"participants"`
	CreatedAt     time.Time                 `json:"created_at"`
	LastHandEnded *time.Time                `json:"last_hand_ended_at"`
}

type TableHistoryParticipant struct {
	AgentID   string `json:"agent_id"`
	AgentName string `json:"agent_name"`
}

type AgentTableResponse struct {
	AgentID string `json:"agent_id"`
	RoomID  string `json:"room_id"`
	TableID string `json:"table_id"`
}

type AgentIdentity struct {
	AgentID   string    `json:"agent_id"`
	Name      string    `json:"name"`
	CreatedAt time.Time `json:"created_at"`
}

type AgentPerformanceSnapshot struct {
	Score         float64    `json:"score"`
	BBPer100      float64    `json:"bb_per_100"`
	NetCCFromPlay int64      `json:"net_cc_from_play"`
	HandsPlayed   int        `json:"hands_played"`
	WinRate       float64    `json:"win_rate"`
	LastActiveAt  *time.Time `json:"last_active_at"`
}

type AgentProfileResponse struct {
	Agent    AgentIdentity            `json:"agent"`
	Stats30D AgentPerformanceSnapshot `json:"stats_30d"`
	StatsAll AgentPerformanceSnapshot `json:"stats_all"`
	Tables   TableHistoryResponse     `json:"tables"`
}

type ReplayResponse struct {
	Items       []ReplayEvent `json:"items"`
	NextFromSeq int64         `json:"next_from_seq"`
	HasMore     bool          `json:"has_more"`
	LastSeq     int64         `json:"last_seq"`
}

type ReplayEvent struct {
	ID           string    `json:"id"`
	TableID      string    `json:"table_id"`
	HandID       string    `json:"hand_id"`
	GlobalSeq    int64     `json:"global_seq"`
	HandSeq      *int32    `json:"hand_seq"`
	EventType    string    `json:"event_type"`
	ActorAgentID string    `json:"actor_agent_id"`
	Payload      any       `json:"payload"`
	SchemaVer    int32     `json:"schema_version"`
	CreatedAt    time.Time `json:"created_at"`
}

type TimelineResponse struct {
	TableID string         `json:"table_id"`
	Items   []TimelineItem `json:"items"`
}

type TimelineItem struct {
	HandID        string     `json:"hand_id"`
	StartSeq      int64      `json:"start_seq"`
	EndSeq        int64      `json:"end_seq"`
	WinnerAgentID string     `json:"winner_agent_id"`
	PotCC         *int64     `json:"pot_cc"`
	StreetEnd     string     `json:"street_end"`
	StartedAt     time.Time  `json:"started_at"`
	EndedAt       *time.Time `json:"ended_at"`
}

type SnapshotResponse struct {
	TableID string         `json:"table_id"`
	AtSeq   int64          `json:"at_seq"`
	State   map[string]any `json:"state"`
	Hit     bool           `json:"-"`
}

type LeaderboardResponse struct {
	Items  []LeaderboardItem `json:"items"`
	Total  int               `json:"total"`
	Limit  int               `json:"limit"`
	Offset int               `json:"offset"`
}

type LeaderboardQuery struct {
	Window string
	RoomID string
	SortBy string
}

type LeaderboardItem struct {
	Rank          int       `json:"rank"`
	AgentID       string    `json:"agent_id"`
	Name          string    `json:"name"`
	Score         float64   `json:"score"`
	BBPer100      float64   `json:"bb_per_100"`
	NetCCFromPlay int64     `json:"net_cc_from_play"`
	HandsPlayed   int       `json:"hands_played"`
	WinRate       float64   `json:"win_rate"`
	LastActiveAt  time.Time `json:"last_active_at"`
}
