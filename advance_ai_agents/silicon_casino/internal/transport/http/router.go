package httptransport

import (
	"expvar"
	"fmt"
	"net/http"
	"os"
	"path/filepath"
	"sort"
	"strings"

	"silicon-casino/internal/agentgateway"
	appagent "silicon-casino/internal/app/agent"
	apppublic "silicon-casino/internal/app/public"
	appsession "silicon-casino/internal/app/session"
	"silicon-casino/internal/config"
	"silicon-casino/internal/mcpserver"
	"silicon-casino/internal/spectatorgateway"
	"silicon-casino/internal/store"

	"github.com/go-chi/chi/v5"
	chimw "github.com/go-chi/chi/v5/middleware"
	"github.com/rs/zerolog/log"
)

func NewRouter(st *store.Store, cfg config.ServerConfig, agentCoord *agentgateway.Coordinator) *chi.Mux {
	agentSvc := appagent.NewService(st, cfg)
	publicSvc := apppublic.NewService(st)
	sessionSvc := appsession.NewService(agentCoord)
	mcpSrv := mcpserver.New(st, cfg, agentCoord)

	agentHandlers := NewAgentHandlers(agentSvc)
	publicHandlers := NewPublicHandlers(publicSvc, sessionSvc)
	adminHandlers := NewAdminHandlers(st)

	r := chi.NewRouter()
	r.Use(chimw.RequestID)
	r.Use(chimw.Recoverer)
	r.Use(chimw.RealIP)

	r.With(APILogMiddleware()).Get("/healthz", adminHandlers.Health())
	r.With(APILogMiddleware()).MethodFunc(http.MethodOptions, "/mcp", func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Allow", "POST, GET, DELETE, OPTIONS")
		w.WriteHeader(http.StatusNoContent)
	})
	r.With(APILogMiddleware()).Method(http.MethodPost, "/mcp", mcpSrv.Handler())
	r.With(APILogMiddleware()).Method(http.MethodGet, "/mcp", mcpSrv.Handler())
	r.With(APILogMiddleware()).Method(http.MethodDelete, "/mcp", mcpSrv.Handler())

	r.Route("/api", func(r chi.Router) {
		r.Use(APILogMiddleware())
		r.Get("/public/leaderboard", publicHandlers.Leaderboard())
		r.Get("/public/rooms", publicHandlers.Rooms())
		r.Get("/public/tables", publicHandlers.Tables())
		r.Get("/public/tables/history", publicHandlers.TableHistory())
		r.Get("/public/tables/{table_id}/replay", publicHandlers.TableReplay())
		r.Get("/public/tables/{table_id}/timeline", publicHandlers.TableTimeline())
		r.Get("/public/tables/{table_id}/snapshot", publicHandlers.TableSnapshot())
		r.Get("/public/agent-table", publicHandlers.AgentTable())
		r.Get("/public/agents/{agent_id}/tables", publicHandlers.AgentTables())
		r.Get("/public/agents/{agent_id}/profile", publicHandlers.AgentProfile())
		r.Get("/public/spectate/events", spectatorgateway.EventsHandler(agentCoord))
		r.Get("/public/spectate/state", spectatorgateway.StateHandler(agentCoord))

		r.Post("/agents/register", agentHandlers.Register())
		r.Post("/agents/claim", agentHandlers.Claim())
		r.Post("/agent/sessions", SessionsCreateHandler(agentCoord))
		r.Delete("/agent/sessions/{session_id}", SessionsDeleteHandler(agentCoord))
		r.Post("/agent/sessions/{session_id}/actions", ActionsHandler(agentCoord))
		r.Get("/agent/sessions/{session_id}/state", StateHandler(agentCoord))
		r.Get("/agent/sessions/{session_id}/events", EventsSSEHandler(agentCoord))

		r.Group(func(r chi.Router) {
			r.Use(AgentAuthMiddleware(st))
			r.Get("/agents/me", agentHandlers.Me())
			r.Post("/agents/bind_key", agentHandlers.BindKey())
		})

		r.Group(func(r chi.Router) {
			r.Use(AdminAuthMiddleware(cfg.AdminAPIKey))
			r.Get("/agents", adminHandlers.Agents())
			r.Get("/ledger", adminHandlers.Ledger())
			r.Post("/topup", adminHandlers.Topup())
			r.Post("/rooms", adminHandlers.Rooms())
			r.MethodFunc(http.MethodGet, "/providers/rates", adminHandlers.ProviderRates())
			r.MethodFunc(http.MethodPost, "/providers/rates", adminHandlers.ProviderRates())

			r.Route("/debug", func(r chi.Router) {
				r.Use(BodyCaptureMiddleware(4096))
				r.Get("/vars", expvar.Handler().ServeHTTP)
			})
		})
	})

	skillServer := http.StripPrefix("/api", http.FileServer(http.Dir(filepath.Join("api", "skill"))))
	r.Handle("/api/skill.md", skillServer)
	r.Handle("/api/messaging.md", skillServer)
	r.Handle("/api/skill.json", skillServer)

	r.With(APILogMiddleware()).Get("/claim/{claim_code}", agentHandlers.ClaimByCode())

	staticDir := filepath.Join("internal", "web", "static")
	if info, err := os.Stat(staticDir); err == nil && info.IsDir() {
		r.Handle("/*", http.FileServer(http.Dir(staticDir)))
	} else {
		log.Warn().Str("path", staticDir).Msg("static directory not found; skipping catch-all static route")
	}
	return r
}

func LogRoutes(r chi.Router) {
	type routeDef struct {
		Method string
		Path   string
	}
	routes := make([]routeDef, 0, 64)
	err := chi.Walk(r, func(method string, route string, _ http.Handler, _ ...func(http.Handler) http.Handler) error {
		routes = append(routes, routeDef{Method: method, Path: route})
		return nil
	})
	if err != nil {
		log.Error().Err(err).Msg("walk routes failed")
		return
	}
	sort.Slice(routes, func(i, j int) bool {
		if routes[i].Path == routes[j].Path {
			return routes[i].Method < routes[j].Method
		}
		return routes[i].Path < routes[j].Path
	})
	var b strings.Builder
	b.WriteString(fmt.Sprintf("Registered routes (%d):\n", len(routes)))
	for _, rt := range routes {
		b.WriteString(fmt.Sprintf("  %-6s %s\n", rt.Method, rt.Path))
	}
	fmt.Print(b.String())
}
