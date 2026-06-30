package agent

import "time"

type RegisterInput struct {
	Name        string
	Description string
}

type RegisterResponse struct {
	Agent struct {
		AgentID          string `json:"agent_id"`
		APIKey           string `json:"api_key"`
		ClaimURL         string `json:"claim_url"`
		VerificationCode string `json:"verification_code"`
	} `json:"agent"`
}

type ClaimInput struct {
	AgentID   string
	ClaimCode string
}

type ClaimResponse struct {
	OK bool `json:"ok"`
}

type ClaimByCodeResponse struct {
	OK      bool   `json:"ok"`
	AgentID string `json:"agent_id"`
	Status  string `json:"status"`
}

type MeResponse struct {
	AgentID   string    `json:"agent_id"`
	Name      string    `json:"name"`
	Status    string    `json:"status"`
	BalanceCC int64     `json:"balance_cc"`
	CreatedAt time.Time `json:"created_at"`
}

type BindKeyInput struct {
	Provider  string
	APIKey    string
	BudgetUSD float64
}

type BindKeyResponse struct {
	OK        bool   `json:"ok"`
	AddedCC   int64  `json:"added_cc,omitempty"`
	BalanceCC int64  `json:"balance_cc,omitempty"`
	Error     string `json:"error,omitempty"`
	Reason    string `json:"reason,omitempty"`
}
