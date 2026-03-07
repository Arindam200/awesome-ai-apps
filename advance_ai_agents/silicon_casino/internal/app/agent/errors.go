package agent

import "errors"

var (
	ErrInvalidRequest            = errors.New("invalid_request")
	ErrInvalidClaim              = errors.New("invalid_claim")
	ErrClaimNotFound             = errors.New("claim_not_found")
	ErrBudgetExceedsLimit        = errors.New("budget_exceeds_limit")
	ErrInvalidProvider           = errors.New("invalid_provider")
	ErrCooldownActive            = errors.New("cooldown_active")
	ErrAPIKeyAlreadyBound        = errors.New("api_key_already_bound")
	ErrInvalidVendorKey          = errors.New("invalid_vendor_key")
	ErrInsufficientVendorBalance = errors.New("insufficient_vendor_balance")
	ErrAgentBlacklisted          = errors.New("agent_blacklisted")
)

type BlacklistError struct {
	Reason string
}

func (e *BlacklistError) Error() string {
	return ErrAgentBlacklisted.Error()
}

func (e *BlacklistError) Unwrap() error {
	return ErrAgentBlacklisted
}
