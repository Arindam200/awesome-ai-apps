package mcpserver

import (
	"context"

	apppublic "silicon-casino/internal/app/public"

	"github.com/mark3labs/mcp-go/mcp"
)

func (s *Server) registerPublicTools() {
	s.mcpServer.AddTool(
		mcp.NewTool(
			"list_rooms",
			mcp.WithDescription("List playable rooms"),
		),
		s.handleListRooms,
	)

	s.mcpServer.AddTool(
		mcp.NewTool(
			"list_live_tables",
			mcp.WithDescription("List live tables with pagination"),
			mcp.WithString("room", mcp.Description("Optional room id")),
			mcp.WithNumber("limit", mcp.Description("Page size, default 50, max 500")),
			mcp.WithNumber("offset", mcp.Description("Page offset, default 0")),
		),
		s.handleListLiveTables,
	)

	s.mcpServer.AddTool(
		mcp.NewTool(
			"get_leaderboard",
			mcp.WithDescription("Get leaderboard"),
			mcp.WithString("window", mcp.Description("7d|30d|all")),
			mcp.WithString("room", mcp.Description("all|low|mid|high")),
			mcp.WithString("sort", mcp.Description("score|net_cc_from_play|hands_played|win_rate")),
			mcp.WithNumber("limit", mcp.Description("Page size, default 50, max 100")),
			mcp.WithNumber("offset", mcp.Description("Page offset, default 0")),
		),
		s.handleGetLeaderboard,
	)

	s.mcpServer.AddTool(
		mcp.NewTool(
			"find_agent_table",
			mcp.WithDescription("Find current table by agent id"),
			mcp.WithString("agent_id", mcp.Required(), mcp.Description("Agent id")),
		),
		s.handleFindAgentTable,
	)
}

func (s *Server) handleListRooms(ctx context.Context, _ mcp.CallToolRequest) (*mcp.CallToolResult, error) {
	resp, err := s.publicSvc.Rooms(ctx)
	if err != nil {
		return mapDomainError(err), nil
	}
	return toolResult(resp), nil
}

func (s *Server) handleListLiveTables(ctx context.Context, request mcp.CallToolRequest) (*mcp.CallToolResult, error) {
	roomID := request.GetString("room", "")
	limit := request.GetInt("limit", defaultPageLimit)
	offset := request.GetInt("offset", 0)
	limit, offset = clampPagination(limit, offset, maxPageLimit)

	resp, err := s.publicSvc.Tables(ctx, roomID, limit, offset)
	if err != nil {
		return mapDomainError(err), nil
	}
	return toolResult(resp), nil
}

func (s *Server) handleGetLeaderboard(ctx context.Context, request mcp.CallToolRequest) (*mcp.CallToolResult, error) {
	window := normalizeLeaderboardWindow(request.GetString("window", ""))
	if !isAllowedLeaderboardWindow(window) {
		return toolError("invalid_request", "window must be 7d|30d|all"), nil
	}
	room := normalizeLeaderboardRoom(request.GetString("room", ""))
	if !isAllowedLeaderboardRoom(room) {
		return toolError("invalid_request", "room must be all|low|mid|high"), nil
	}
	sortBy := normalizeLeaderboardSort(request.GetString("sort", ""))
	if !isAllowedLeaderboardSort(sortBy) {
		return toolError("invalid_request", "sort must be score|net_cc_from_play|hands_played|win_rate"), nil
	}
	limit := request.GetInt("limit", defaultPageLimit)
	offset := request.GetInt("offset", 0)
	limit, offset = clampPagination(limit, offset, maxLeaderboardLimit)

	resp, err := s.publicSvc.Leaderboard(ctx, apppublic.LeaderboardQuery{
		Window: window,
		RoomID: room,
		SortBy: sortBy,
	}, limit, offset)
	if err != nil {
		return mapDomainError(err), nil
	}
	return toolResult(resp), nil
}

func (s *Server) handleFindAgentTable(ctx context.Context, request mcp.CallToolRequest) (*mcp.CallToolResult, error) {
	agentID, err := request.RequireString("agent_id")
	if err != nil {
		return toolError("invalid_request", err.Error()), nil
	}
	resp, svcErr := s.sessionSvc.FindTableByAgent(agentID)
	if svcErr != nil {
		return mapDomainError(svcErr), nil
	}
	return toolResult(resp), nil
}
