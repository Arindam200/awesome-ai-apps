package mcpserver

import (
	"context"
	"strings"

	"silicon-casino/internal/agentgateway"
	"silicon-casino/internal/game/viewmodel"

	"github.com/mark3labs/mcp-go/mcp"
)

func (s *Server) registerGameplayTools() {
	s.mcpServer.AddTool(
		mcp.NewTool(
			"next_decision",
			mcp.WithDescription("Session-aware decision fetch. Creates/reuses session and returns either decision_request or noop."),
			mcp.WithString("agent_id", mcp.Required(), mcp.Description("Agent id")),
			mcp.WithString("api_key", mcp.Required(), mcp.Description("Agent api key")),
			mcp.WithString("mode", mcp.Description("random|select, default random")),
			mcp.WithString("room", mcp.Description("Room id when mode=select")),
		),
		s.handleNextDecision,
	)

	s.mcpServer.AddTool(
		mcp.NewTool(
			"submit_next_decision",
			mcp.WithDescription("Submit action by decision_id from next_decision."),
			mcp.WithString("agent_id", mcp.Required(), mcp.Description("Agent id")),
			mcp.WithString("api_key", mcp.Required(), mcp.Description("Agent api key")),
			mcp.WithString("decision_id", mcp.Required(), mcp.Description("Decision id from next_decision")),
			mcp.WithString("action", mcp.Required(), mcp.Description("fold|check|call|bet|raise")),
			mcp.WithNumber("amount", mcp.Description("Required for bet/raise")),
			mcp.WithString("thought", mcp.Description("Optional thought log for spectator UI")),
		),
		s.handleSubmitNextDecision,
	)
}

func (s *Server) handleNextDecision(ctx context.Context, request mcp.CallToolRequest) (*mcp.CallToolResult, error) {
	agentID, err := request.RequireString("agent_id")
	if err != nil {
		return toolError("invalid_request", err.Error()), nil
	}
	apiKey, err := request.RequireString("api_key")
	if err != nil {
		return toolError("invalid_request", err.Error()), nil
	}
	if _, authErr := s.authAgent(ctx, agentID, apiKey); authErr != nil {
		return authErr, nil
	}
	mode := normalizeJoinMode(request.GetString("mode", ""))
	roomID := request.GetString("room", "")

	var session *agentgateway.CreateSessionResponse
	if existing, ok := s.coord.FindOpenSessionByAgent(agentID); ok {
		session = existing
	} else {
		created, createErr := s.coord.CreateSession(ctx, agentgateway.CreateSessionRequest{
			AgentID:  agentID,
			APIKey:   apiKey,
			JoinMode: mode,
			RoomID:   roomID,
		})
		if createErr != nil {
			if _, code := agentgateway.MapSessionCreateError(createErr); code == "agent_already_in_session" {
				if existing, ok := s.coord.FindOpenSessionByAgent(agentID); ok {
					session = existing
				} else {
					return toolResult(map[string]any{
						"type":           "noop",
						"status":         "session_recovering",
						"recoverable":    true,
						"retry_after_ms": 1000,
					}), nil
				}
			} else {
				return sessionCreateError(createErr), nil
			}
		} else {
			session = created
		}
	}

	if session == nil {
		return toolResult(map[string]any{
			"type":           "noop",
			"status":         "session_recovering",
			"recoverable":    true,
			"retry_after_ms": 1000,
		}), nil
	}
	if strings.TrimSpace(session.TableID) == "" {
		return toolResult(map[string]any{
			"type":           "noop",
			"status":         "waiting_matchmaking",
			"session_id":     session.SessionID,
			"room_id":        session.RoomID,
			"recoverable":    true,
			"retry_after_ms": 1000,
		}), nil
	}
	state, stateErr := s.coord.GetState(session.SessionID)
	if stateErr != nil {
		if agentgateway.IsSessionNotFound(stateErr) {
			return toolResult(map[string]any{
				"type":           "noop",
				"status":         "session_recovering",
				"session_id":     session.SessionID,
				"table_id":       session.TableID,
				"recoverable":    true,
				"retry_after_ms": 1000,
			}), nil
		}
		return toolError("internal_error", stateErr.Error()), nil
	}
	if state.TableStatus == "closing" {
		return toolResult(map[string]any{
			"type":       "noop",
			"status":     "table_closing",
			"session_id": session.SessionID,
			"table_id":   session.TableID,
			"room_id":    session.RoomID,
			"table": map[string]any{
				"status":                state.TableStatus,
				"reconnect_deadline_ts": state.ReconnectDeadlineTS,
				"close_reason":          state.CloseReason,
			},
			"recoverable":    true,
			"retry_after_ms": 1000,
		}), nil
	}
	if len(state.LegalActions) == 0 || strings.TrimSpace(state.TurnID) == "" {
		return toolResult(map[string]any{
			"type":       "noop",
			"status":     "waiting_opponent",
			"session_id": session.SessionID,
			"table_id":   session.TableID,
			"room_id":    session.RoomID,
			"table": map[string]any{
				"status":                state.TableStatus,
				"reconnect_deadline_ts": state.ReconnectDeadlineTS,
				"close_reason":          state.CloseReason,
			},
			"recoverable":    true,
			"retry_after_ms": 1000,
		}), nil
	}

	pending := s.storePendingDecision(agentID, session.SessionID, state.TurnID, state.ActionTimeoutMS)
	return toolResult(map[string]any{
		"type":             "decision_request",
		"status":           "decision_ready",
		"decision_id":      pending.DecisionID,
		"decision_expires": pending.ExpiresAt,
		"session_id":       session.SessionID,
		"table_id":         session.TableID,
		"room_id":          session.RoomID,
		"state":            buildDecisionStatePayload(session.SessionID, state),
	}), nil
}

func (s *Server) handleSubmitNextDecision(ctx context.Context, request mcp.CallToolRequest) (*mcp.CallToolResult, error) {
	agentID, err := request.RequireString("agent_id")
	if err != nil {
		return toolError("invalid_request", err.Error()), nil
	}
	apiKey, err := request.RequireString("api_key")
	if err != nil {
		return toolError("invalid_request", err.Error()), nil
	}
	if _, authErr := s.authAgent(ctx, agentID, apiKey); authErr != nil {
		return authErr, nil
	}
	decisionID, err := request.RequireString("decision_id")
	if err != nil {
		return toolError("invalid_request", err.Error()), nil
	}
	pending, ok := s.getPendingDecision(decisionID)
	if !ok {
		return toolError("pending_decision_not_found", "decision_id is missing, expired, or already consumed"), nil
	}
	if pending.AgentID != agentID {
		return toolError("unauthorized", "decision_id does not belong to this agent"), nil
	}
	action, err := request.RequireString("action")
	if err != nil {
		return toolError("invalid_request", err.Error()), nil
	}
	thought := request.GetString("thought", "")

	var amount *int64
	if request.GetArguments()["amount"] != nil {
		v, convErr := request.RequireFloat("amount")
		if convErr != nil {
			return toolError("invalid_request", convErr.Error()), nil
		}
		iv := int64(v)
		amount = &iv
	}

	res, submitErr := s.coord.SubmitAction(ctx, pending.SessionID, agentgateway.ActionRequest{
		RequestID:  pending.DecisionID,
		TurnID:     pending.TurnID,
		Action:     action,
		Amount:     amount,
		ThoughtLog: thought,
	})
	if submitErr != nil {
		if _, code := agentgateway.MapActionSubmitError(submitErr); code == "invalid_turn_id" || code == "table_closed" || code == "table_closing" {
			s.deletePendingDecision(decisionID)
			return toolError("stale_decision", submitErr.Error()), nil
		}
		return actionSubmitError(submitErr), nil
	}
	s.deletePendingDecision(decisionID)
	return toolResult(res), nil
}

func buildDecisionStatePayload(sessionID string, state viewmodel.AgentStateView) map[string]any {
	return map[string]any{
		"session_id":         sessionID,
		"hand_id":            state.HandID,
		"street":             state.Street,
		"pot":                state.Pot,
		"board":              state.CommunityCards,
		"legal_actions":      state.LegalActions,
		"action_constraints": state.ActionConstraints,
		"turn": map[string]any{
			"id":         state.TurnID,
			"actor_seat": state.CurrentActorSeat,
			"timeout_ms": state.ActionTimeoutMS,
		},
		"hero": map[string]any{
			"seat":       state.MySeat,
			"balance":    state.MyBalance,
			"hole_cards": state.MyHoleCards,
		},
		"seats": state.Seats,
		"table": map[string]any{
			"status":                state.TableStatus,
			"reconnect_deadline_ts": state.ReconnectDeadlineTS,
			"close_reason":          state.CloseReason,
		},
	}
}
