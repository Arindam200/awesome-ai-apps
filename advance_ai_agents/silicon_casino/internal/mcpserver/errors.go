package mcpserver

import (
	"errors"
	"fmt"

	"silicon-casino/internal/agentgateway"
	appagent "silicon-casino/internal/app/agent"
	apppublic "silicon-casino/internal/app/public"
	appsession "silicon-casino/internal/app/session"
	"silicon-casino/internal/store"

	"github.com/mark3labs/mcp-go/mcp"
)

func toolResult(data any) *mcp.CallToolResult {
	return mcp.NewToolResultStructuredOnly(data)
}

func toolError(code, message string) *mcp.CallToolResult {
	result := mcp.NewToolResultStructured(
		map[string]any{
			"error": map[string]any{
				"code":    code,
				"message": message,
			},
		},
		fmt.Sprintf("%s: %s", code, message),
	)
	result.IsError = true
	return result
}

func sessionCreateError(err error) *mcp.CallToolResult {
	if err == nil {
		return toolError("internal_error", "unknown session create error")
	}
	_, code := agentgateway.MapSessionCreateError(err)
	return toolError(code, err.Error())
}

func actionSubmitError(err error) *mcp.CallToolResult {
	if err == nil {
		return toolError("internal_error", "unknown action error")
	}
	_, code := agentgateway.MapActionSubmitError(err)
	return toolError(code, err.Error())
}

func mapDomainError(err error) *mcp.CallToolResult {
	switch {
	case err == nil:
		return toolError("internal_error", "unknown error")
	case errors.Is(err, appagent.ErrInvalidRequest),
		errors.Is(err, apppublic.ErrInvalidRequest),
		errors.Is(err, appsession.ErrInvalidRequest):
		return toolError("invalid_request", err.Error())
	case errors.Is(err, appagent.ErrInvalidClaim):
		return toolError("invalid_claim", err.Error())
	case errors.Is(err, appagent.ErrClaimNotFound):
		return toolError("claim_not_found", err.Error())
	case errors.Is(err, appagent.ErrBudgetExceedsLimit):
		return toolError("budget_exceeds_limit", err.Error())
	case errors.Is(err, appagent.ErrInvalidProvider):
		return toolError("invalid_provider", err.Error())
	case errors.Is(err, appagent.ErrCooldownActive):
		return toolError("cooldown_active", err.Error())
	case errors.Is(err, appagent.ErrAPIKeyAlreadyBound):
		return toolError("api_key_already_bound", err.Error())
	case errors.Is(err, appagent.ErrInvalidVendorKey):
		return toolError("invalid_vendor_key", err.Error())
	case errors.Is(err, appagent.ErrInsufficientVendorBalance):
		return toolError("insufficient_vendor_balance", err.Error())
	case errors.Is(err, appagent.ErrAgentBlacklisted):
		var be *appagent.BlacklistError
		if errors.As(err, &be) && be.Reason != "" {
			return toolError("agent_blacklisted", be.Reason)
		}
		return toolError("agent_blacklisted", err.Error())
	case errors.Is(err, apppublic.ErrTableNotFound), errors.Is(err, appsession.ErrTableNotFound), errors.Is(err, store.ErrNotFound):
		return toolError("not_found", err.Error())
	default:
		return toolError("internal_error", err.Error())
	}
}
