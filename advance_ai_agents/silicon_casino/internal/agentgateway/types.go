package agentgateway

import "time"

type CreateSessionRequest struct {
	AgentID  string `json:"agent_id"`
	APIKey   string `json:"api_key"`
	JoinMode string `json:"join_mode"`
	RoomID   string `json:"room_id,omitempty"`
}

type CreateSessionResponse struct {
	SessionID string    `json:"session_id"`
	TableID   string    `json:"table_id,omitempty"`
	RoomID    string    `json:"room_id"`
	SeatID    *int      `json:"seat_id,omitempty"`
	StreamURL string    `json:"stream_url"`
	ExpiresAt time.Time `json:"expires_at"`
}

type ActionRequest struct {
	RequestID  string `json:"request_id"`
	TurnID     string `json:"turn_id"`
	Action     string `json:"action"`
	Amount     *int64 `json:"amount,omitempty"`
	ThoughtLog string `json:"thought_log,omitempty"`
}

type ActionResponse struct {
	Accepted  bool   `json:"accepted"`
	RequestID string `json:"request_id"`
	Reason    string `json:"reason,omitempty"`
}

type ErrorResponse struct {
	Error string `json:"error"`
}
