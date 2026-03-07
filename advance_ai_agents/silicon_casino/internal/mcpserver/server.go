package mcpserver

import (
	"context"
	"encoding/json"
	"net/http"
	"strconv"
	"strings"
	"sync"
	"sync/atomic"
	"time"

	"silicon-casino/internal/agentgateway"
	appagent "silicon-casino/internal/app/agent"
	apppublic "silicon-casino/internal/app/public"
	appsession "silicon-casino/internal/app/session"
	"silicon-casino/internal/config"
	"silicon-casino/internal/store"

	"github.com/mark3labs/mcp-go/mcp"
	"github.com/mark3labs/mcp-go/server"
)

type Server struct {
	store      *store.Store
	coord      *agentgateway.Coordinator
	agentSvc   *appagent.Service
	publicSvc  *apppublic.Service
	sessionSvc *appsession.Service

	mcpServer  *server.MCPServer
	httpServer *server.StreamableHTTPServer

	decisionMu   sync.Mutex
	decisionSeq  atomic.Uint64
	decisionByID map[string]pendingDecision
}

type pendingDecision struct {
	DecisionID string
	AgentID    string
	SessionID  string
	TurnID     string
	ExpiresAt  time.Time
}

func New(st *store.Store, cfg config.ServerConfig, coord *agentgateway.Coordinator) *Server {
	mcpSrv := server.NewMCPServer(
		"silicon-casino",
		"0.1.0",
		server.WithToolCapabilities(false),
		server.WithResourceCapabilities(false, false),
		server.WithRecovery(),
		server.WithResourceRecovery(),
	)
	s := &Server{
		store:        st,
		coord:        coord,
		agentSvc:     appagent.NewService(st, cfg),
		publicSvc:    apppublic.NewService(st),
		sessionSvc:   appsession.NewService(coord),
		mcpServer:    mcpSrv,
		httpServer:   server.NewStreamableHTTPServer(mcpSrv, server.WithStateLess(true), server.WithDisableStreaming(true)),
		decisionByID: make(map[string]pendingDecision),
	}
	s.registerPublicTools()
	s.registerMatchmakingTools()
	s.registerGameplayTools()
	s.registerResources()
	return s
}

func (s *Server) Handler() http.Handler {
	return s.httpServer
}

func (s *Server) registerResources() {
	s.mcpServer.AddResourceTemplate(
		mcp.NewResourceTemplate(
			"table://{table_id}/public_state",
			"table_public_state",
			mcp.WithTemplateDescription("Public table state by table id (future MCP streaming extension anchor)"),
			mcp.WithTemplateMIMEType("application/json"),
		),
		func(ctx context.Context, request mcp.ReadResourceRequest) ([]mcp.ResourceContents, error) {
			uri := request.Params.URI
			raw := string(uri)
			if !strings.HasPrefix(raw, "table://") || !strings.HasSuffix(raw, "/public_state") {
				return nil, nil
			}
			tableID := strings.TrimPrefix(raw, "table://")
			tableID = strings.TrimSuffix(tableID, "/public_state")
			if tableID == "" {
				return nil, nil
			}
			state, err := s.coord.GetPublicState(tableID)
			if err != nil {
				return nil, err
			}
			payload, err := json.Marshal(map[string]any{
				"table_id": tableID,
				"state":    state,
			})
			if err != nil {
				return nil, err
			}
			return []mcp.ResourceContents{
				mcp.TextResourceContents{
					URI:      raw,
					MIMEType: "application/json",
					Text:     string(payload),
				},
			}, nil
		},
	)
}

func (s *Server) authAgent(ctx context.Context, agentID, apiKey string) (*store.Agent, *mcp.CallToolResult) {
	agentID = strings.TrimSpace(agentID)
	apiKey = strings.TrimSpace(apiKey)
	if agentID == "" || apiKey == "" {
		return nil, toolError("invalid_request", "agent_id and api_key are required")
	}
	agent, err := s.store.GetAgentByAPIKey(ctx, apiKey)
	if err != nil {
		return nil, toolError("unauthorized", "invalid api_key")
	}
	if agent.ID != agentID {
		return nil, toolError("unauthorized", "agent_id does not match api_key")
	}
	return agent, nil
}

func (s *Server) authSessionOwner(ctx context.Context, agentID, apiKey, sessionID string) (*mcp.CallToolResult, bool) {
	_, errResp := s.authAgent(ctx, agentID, apiKey)
	if errResp != nil {
		return errResp, false
	}
	state, err := s.coord.GetState(sessionID)
	if err != nil {
		if agentgateway.IsSessionNotFound(err) {
			return toolError("session_not_found", err.Error()), false
		}
		return toolError("internal_error", err.Error()), false
	}
	ownerID := ""
	for _, seat := range state.Seats {
		if seat.SeatID == state.MySeat {
			ownerID = seat.AgentID
			break
		}
	}
	if ownerID == "" {
		return toolError("session_not_found", "unable to resolve session owner"), false
	}
	if ownerID != agentID {
		return toolError("unauthorized", "session does not belong to this agent"), false
	}
	return nil, true
}

func (s *Server) storePendingDecision(agentID, sessionID, turnID string, timeoutMS int64) pendingDecision {
	if timeoutMS <= 0 {
		timeoutMS = 15_000
	}
	id := "dec_" + strconv.FormatUint(s.decisionSeq.Add(1), 10)
	d := pendingDecision{
		DecisionID: id,
		AgentID:    agentID,
		SessionID:  sessionID,
		TurnID:     turnID,
		ExpiresAt:  time.Now().Add(time.Duration(timeoutMS) * time.Millisecond),
	}
	s.decisionMu.Lock()
	s.decisionByID[id] = d
	s.decisionMu.Unlock()
	return d
}

func (s *Server) getPendingDecision(decisionID string) (pendingDecision, bool) {
	s.decisionMu.Lock()
	defer s.decisionMu.Unlock()
	d, ok := s.decisionByID[decisionID]
	if !ok {
		return pendingDecision{}, false
	}
	if time.Now().After(d.ExpiresAt) {
		delete(s.decisionByID, decisionID)
		return pendingDecision{}, false
	}
	return d, true
}

func (s *Server) deletePendingDecision(decisionID string) {
	s.decisionMu.Lock()
	delete(s.decisionByID, decisionID)
	s.decisionMu.Unlock()
}
