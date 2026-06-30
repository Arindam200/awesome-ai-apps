package mcpserver

import (
	"context"

	appagent "silicon-casino/internal/app/agent"

	"github.com/mark3labs/mcp-go/mcp"
)

func (s *Server) registerMatchmakingTools() {
	s.mcpServer.AddTool(
		mcp.NewTool(
			"register_agent",
			mcp.WithDescription("Register a new agent"),
			mcp.WithString("name", mcp.Required(), mcp.Description("Agent name")),
			mcp.WithString("profile", mcp.Description("Optional profile/description")),
		),
		s.handleRegisterAgent,
	)

	s.mcpServer.AddTool(
		mcp.NewTool(
			"claim_agent",
			mcp.WithDescription("Claim an agent account with claim code"),
			mcp.WithString("agent_id", mcp.Required(), mcp.Description("Agent id")),
			mcp.WithString("claim_code", mcp.Required(), mcp.Description("Claim code")),
		),
		s.handleClaimAgent,
	)

	s.mcpServer.AddTool(
		mcp.NewTool(
			"bind_vendor_key",
			mcp.WithDescription("Bind and verify a vendor key to top up credits"),
			mcp.WithString("agent_id", mcp.Required(), mcp.Description("Agent id")),
			mcp.WithString("api_key", mcp.Required(), mcp.Description("Agent api key")),
			mcp.WithString("provider", mcp.Required(), mcp.Description("openai|kimi")),
			mcp.WithString("vendor_key", mcp.Required(), mcp.Description("Vendor API key")),
			mcp.WithNumber("budget_usd", mcp.Required(), mcp.Description("Top-up budget in USD")),
		),
		s.handleBindVendorKey,
	)
}

func (s *Server) handleRegisterAgent(ctx context.Context, request mcp.CallToolRequest) (*mcp.CallToolResult, error) {
	name, err := request.RequireString("name")
	if err != nil {
		return toolError("invalid_request", err.Error()), nil
	}
	profile := request.GetString("profile", "")
	resp, svcErr := s.agentSvc.Register(ctx, appagent.RegisterInput{Name: name, Description: profile})
	if svcErr != nil {
		return mapDomainError(svcErr), nil
	}
	return toolResult(resp), nil
}

func (s *Server) handleClaimAgent(ctx context.Context, request mcp.CallToolRequest) (*mcp.CallToolResult, error) {
	agentID, err := request.RequireString("agent_id")
	if err != nil {
		return toolError("invalid_request", err.Error()), nil
	}
	claimCode, err := request.RequireString("claim_code")
	if err != nil {
		return toolError("invalid_request", err.Error()), nil
	}
	resp, svcErr := s.agentSvc.Claim(ctx, appagent.ClaimInput{AgentID: agentID, ClaimCode: claimCode})
	if svcErr != nil {
		return mapDomainError(svcErr), nil
	}
	return toolResult(resp), nil
}

func (s *Server) handleBindVendorKey(ctx context.Context, request mcp.CallToolRequest) (*mcp.CallToolResult, error) {
	agentID, err := request.RequireString("agent_id")
	if err != nil {
		return toolError("invalid_request", err.Error()), nil
	}
	apiKey, err := request.RequireString("api_key")
	if err != nil {
		return toolError("invalid_request", err.Error()), nil
	}
	agent, authErr := s.authAgent(ctx, agentID, apiKey)
	if authErr != nil {
		return authErr, nil
	}
	provider, err := request.RequireString("provider")
	if err != nil {
		return toolError("invalid_request", err.Error()), nil
	}
	vendorKey, err := request.RequireString("vendor_key")
	if err != nil {
		return toolError("invalid_request", err.Error()), nil
	}
	budgetUSD, err := request.RequireFloat("budget_usd")
	if err != nil {
		return toolError("invalid_request", err.Error()), nil
	}

	resp, svcErr := s.agentSvc.BindKey(ctx, agent, appagent.BindKeyInput{
		Provider:  provider,
		APIKey:    vendorKey,
		BudgetUSD: budgetUSD,
	})
	if svcErr != nil {
		return mapDomainError(svcErr), nil
	}
	return toolResult(resp), nil
}
