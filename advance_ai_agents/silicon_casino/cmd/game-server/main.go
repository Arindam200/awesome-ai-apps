package main

import (
	"bytes"
	"context"
	"encoding/json"
	"expvar"
	"fmt"
	"io"
	"log/slog"
	"net/http"
	"path/filepath"
	"sort"
	"strconv"
	"strings"
	"time"

	"silicon-casino/internal/agentgateway"
	"silicon-casino/internal/config"
	"silicon-casino/internal/ledger"
	"silicon-casino/internal/logging"
	"silicon-casino/internal/spectatorgateway"
	"silicon-casino/internal/store"

	"github.com/go-chi/chi/v5"
	chimw "github.com/go-chi/chi/v5/middleware"
	"github.com/go-chi/httplog/v3"
	"github.com/rs/zerolog/log"
)

var (
	replayQueryTotal        = expvar.NewInt("replay_query_total")
	replayQueryErrorsTotal  = expvar.NewInt("replay_query_errors_total")
	replayQueryP95MS        = expvar.NewInt("replay_query_p95_ms")
	replaySnapshotRebuildMS = expvar.NewInt("replay_snapshot_rebuild_ms")
	replaySnapshotHitTotal  = expvar.NewInt("replay_snapshot_hit_total")
	replaySnapshotMissTotal = expvar.NewInt("replay_snapshot_miss_total")
	replaySnapshotHitRatio  = expvar.NewFloat("replay_snapshot_hit_ratio")
)

func main() {
	logCfg, err := config.LoadLog()
	if err != nil {
		panic(err)
	}
	logging.Init(logCfg)
	cfg, err := config.LoadServer()
	if err != nil {
		log.Fatal().Err(err).Msg("load server config failed")
	}
	initial := int64(100000)

	st, err := store.New(cfg.PostgresDSN)
	if err != nil {
		log.Fatal().Err(err).Msg("store init failed")
	}
	if err := st.Ping(context.Background()); err != nil {
		log.Fatal().Err(err).Msg("db ping failed")
	}

	// Optional seed from env
	seedAgent(st, cfg.Agent1Name, cfg.Agent1Key, initial)
	seedAgent(st, cfg.Agent2Name, cfg.Agent2Key, initial)

	led := ledger.New(st)
	if err := st.EnsureDefaultRooms(context.Background()); err != nil {
		log.Fatal().Err(err).Msg("ensure default rooms failed")
	}
	if err := st.EnsureDefaultProviderRates(context.Background(), defaultProviderRates(cfg)); err != nil {
		log.Fatal().Err(err).Msg("ensure provider rates failed")
	}
	agentCoord := agentgateway.NewCoordinator(st, led)
	agentCoord.StartJanitor(context.Background(), time.Minute)
	r := newRouter(st, cfg, agentCoord)
	logRoutes(r)

	server := &http.Server{
		Addr:              cfg.HTTPAddr,
		Handler:           r,
		ReadHeaderTimeout: 5 * time.Second,
		ReadTimeout:       10 * time.Second,
		IdleTimeout:       120 * time.Second,
	}
	log.Info().Str("addr", cfg.HTTPAddr).Msg("http listening")
	log.Fatal().Err(server.ListenAndServe()).Msg("server stopped")
}

func newRouter(st *store.Store, cfg config.ServerConfig, agentCoord *agentgateway.Coordinator) *chi.Mux {
	r := chi.NewRouter()
	r.Use(chimw.RequestID)
	r.Use(chimw.Recoverer)
	r.Use(chimw.RealIP)

	r.With(apiLogMiddleware()).Get("/healthz", healthHandler(st))

	r.Route("/api", func(r chi.Router) {
		r.Use(apiLogMiddleware())
		r.Use(bodyCaptureMiddleware())
		r.Get("/public/leaderboard", publicLeaderboardHandler(st))
		r.Get("/public/rooms", publicRoomsHandler(st))
		r.Get("/public/tables", publicTablesHandler(st))
		r.Get("/public/tables/history", publicTableHistoryHandler(st))
		r.Get("/public/tables/{table_id}/replay", publicTableReplayHandler(st))
		r.Get("/public/tables/{table_id}/timeline", publicTableTimelineHandler(st))
		r.Get("/public/tables/{table_id}/snapshot", publicTableSnapshotHandler(st))
		r.Get("/public/agent-table", publicAgentTableHandler(agentCoord))
		r.Get("/public/agents/{agent_id}/tables", publicAgentTablesHandler(st))
		r.Get("/public/spectate/events", spectatorgateway.EventsHandler(agentCoord))
		r.Get("/public/spectate/state", spectatorgateway.StateHandler(agentCoord))

		r.Post("/agents/register", registerAgentHandler(st))
		r.Post("/agents/claim", claimAgentHandler(st))
		r.Post("/agent/sessions", agentgateway.SessionsCreateHandler(agentCoord))
		r.Delete("/agent/sessions/{session_id}", agentgateway.SessionsDeleteHandler(agentCoord))
		r.Post("/agent/sessions/{session_id}/actions", agentgateway.ActionsHandler(agentCoord))
		r.Get("/agent/sessions/{session_id}/state", agentgateway.StateHandler(agentCoord))
		r.Get("/agent/sessions/{session_id}/events", agentgateway.EventsSSEHandler(agentCoord))

		r.Group(func(r chi.Router) {
			r.Use(agentAuthMiddleware(st))
			r.Get("/agents/me", agentMeHandler(st))
			r.Post("/agents/bind_key", bindKeyHandler(st, cfg))
		})

		r.Group(func(r chi.Router) {
			r.Use(adminAuthMiddleware(cfg.AdminAPIKey))
			r.Get("/agents", agentsHandler(st))
			r.Get("/ledger", ledgerHandler(st))
			r.Post("/topup", topupHandler(st))
			r.Post("/rooms", roomsHandler(st))
			r.Get("/debug/vars", expvar.Handler().ServeHTTP)
			r.MethodFunc(http.MethodGet, "/providers/rates", providerRatesHandler(st))
			r.MethodFunc(http.MethodPost, "/providers/rates", providerRatesHandler(st))
		})
	})

	skillServer := http.StripPrefix("/api", http.FileServer(http.Dir(filepath.Join("api", "skill"))))
	r.Handle("/api/skill.md", skillServer)
	r.Handle("/api/messaging.md", skillServer)
	r.Handle("/api/skill.json", skillServer)

	r.With(apiLogMiddleware(), bodyCaptureMiddleware()).Get("/claim/{claim_code}", claimByCodeHandler(st))

	staticDir := filepath.Join("internal", "web", "static")
	r.Handle("/*", http.FileServer(http.Dir(staticDir)))
	return r
}

func apiLogMiddleware() func(http.Handler) http.Handler {
	return httplog.RequestLogger(
		slog.New(slog.NewJSONHandler(logging.Writer(), &slog.HandlerOptions{})),
		&httplog.Options{
			Level:              slog.LevelInfo,
			Schema:             httplog.Schema{ResponseStatus: "status", ResponseDuration: "duration_ms"},
			LogRequestBody:     func(*http.Request) bool { return false },
			LogResponseBody:    func(*http.Request) bool { return false },
			LogRequestHeaders:  []string{},
			LogResponseHeaders: []string{},
			LogExtraAttrs: func(req *http.Request, _ string, _ int) []slog.Attr {
				rc := chi.RouteContext(req.Context())
				route := req.URL.Path
				if rc != nil && rc.RoutePattern() != "" {
					route = rc.RoutePattern()
				}
				return []slog.Attr{
					slog.String("request_id", chimw.GetReqID(req.Context())),
					slog.String("method", req.Method),
					slog.String("route", route),
					slog.String("path", req.URL.Path),
				}
			},
		},
	)
}

func bodyCaptureMiddleware() func(http.Handler) http.Handler {
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			if isSSERequest(r) {
				next.ServeHTTP(w, r)
				return
			}
			reqBody, err := io.ReadAll(r.Body)
			if err != nil {
				reqBody = nil
			}
			r.Body = io.NopCloser(bytes.NewReader(reqBody))

			cw := &captureWriter{ResponseWriter: w}
			next.ServeHTTP(cw, r)

			if len(reqBody) > 0 {
				httplog.SetAttrs(r.Context(), slog.Any("request_body", parseMaybeJSON(reqBody)))
			} else {
				httplog.SetAttrs(r.Context(), slog.Any("request_body", ""))
			}
			httplog.SetAttrs(r.Context(), slog.Any("response_body", parseMaybeJSON(cw.body.Bytes())))
		})
	}
}

type captureWriter struct {
	http.ResponseWriter
	body bytes.Buffer
}

func (c *captureWriter) Write(p []byte) (int, error) {
	_, _ = c.body.Write(p)
	return c.ResponseWriter.Write(p)
}

func (c *captureWriter) Flush() {
	if f, ok := c.ResponseWriter.(http.Flusher); ok {
		f.Flush()
	}
}

func parseMaybeJSON(b []byte) any {
	if len(b) == 0 {
		return ""
	}
	var out any
	if err := json.Unmarshal(b, &out); err == nil {
		return out
	}
	return string(b)
}

func writeHTTPError(w http.ResponseWriter, status int, code string) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(map[string]any{"error": code})
}

func isSSERequest(r *http.Request) bool {
	if strings.Contains(r.Header.Get("Accept"), "text/event-stream") {
		return true
	}
	path := r.URL.Path
	if strings.HasSuffix(path, "/events") && strings.Contains(path, "/api/agent/sessions/") {
		return true
	}
	if path == "/api/public/spectate/events" {
		return true
	}
	return false
}

func logRoutes(r chi.Router) {
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

func seedAgent(st *store.Store, name, key string, initial int64) {
	if name == "" || key == "" {
		return
	}
	ctx := context.Background()
	agent, err := st.GetAgentByAPIKey(ctx, key)
	if err == nil && agent != nil {
		return
	}
	id, err := st.CreateAgent(ctx, name, key, "claim_"+key)
	if err != nil {
		log.Error().Err(err).Msg("seed agent error")
		return
	}
	_ = st.EnsureAccount(ctx, id, initial)
}

func defaultProviderRates(cfg config.ServerConfig) []store.ProviderRate {
	ccPerUSD := cfg.CCPerUSD
	return []store.ProviderRate{
		{
			Provider:            "openai",
			PricePer1KTokensUSD: cfg.OpenAIPricePer1K,
			CCPerUSD:            ccPerUSD,
			Weight:              cfg.OpenAIWeight,
		},
		{
			Provider:            "kimi",
			PricePer1KTokensUSD: cfg.KimiPricePer1K,
			CCPerUSD:            ccPerUSD,
			Weight:              cfg.KimiWeight,
		},
	}
}

func healthHandler(st *store.Store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		if err := st.Ping(r.Context()); err != nil {
			w.WriteHeader(http.StatusServiceUnavailable)
			_ = json.NewEncoder(w).Encode(map[string]any{"ok": false, "db": "down"})
			return
		}
		_ = json.NewEncoder(w).Encode(map[string]any{"ok": true, "db": "up"})
	}
}

func agentsHandler(st *store.Store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		limit, offset := parsePagination(r)
		items, err := st.ListAgents(r.Context(), limit, offset)
		if err != nil {
			writeHTTPError(w, http.StatusInternalServerError, "internal_error")
			return
		}
		_ = json.NewEncoder(w).Encode(map[string]any{
			"items":  items,
			"limit":  limit,
			"offset": offset,
		})
	}
}

func ledgerHandler(st *store.Store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		limit, offset := parsePagination(r)
		f := store.LedgerFilter{
			AgentID: r.URL.Query().Get("agent_id"),
			HandID:  r.URL.Query().Get("hand_id"),
		}
		if v := r.URL.Query().Get("from"); v != "" {
			if t, err := time.Parse(time.RFC3339, v); err == nil {
				f.From = &t
			}
		}
		if v := r.URL.Query().Get("to"); v != "" {
			if t, err := time.Parse(time.RFC3339, v); err == nil {
				f.To = &t
			}
		}
		items, err := st.ListLedgerEntries(r.Context(), f, limit, offset)
		if err != nil {
			writeHTTPError(w, http.StatusInternalServerError, "internal_error")
			return
		}
		_ = json.NewEncoder(w).Encode(map[string]any{
			"items":  items,
			"limit":  limit,
			"offset": offset,
		})
	}
}

func topupHandler(st *store.Store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			writeHTTPError(w, http.StatusMethodNotAllowed, "method_not_allowed")
			return
		}
		var body struct {
			AgentID  string `json:"agent_id"`
			AmountCC int64  `json:"amount_cc"`
		}
		if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
			writeHTTPError(w, http.StatusBadRequest, "invalid_json")
			return
		}
		if body.AgentID == "" || body.AmountCC <= 0 {
			writeHTTPError(w, http.StatusBadRequest, "invalid_request")
			return
		}
		refID := strconv.FormatInt(time.Now().UnixNano(), 10)
		bal, err := st.Credit(r.Context(), body.AgentID, body.AmountCC, "topup_credit", "topup", refID)
		if err != nil {
			writeHTTPError(w, http.StatusInternalServerError, "internal_error")
			return
		}
		_ = json.NewEncoder(w).Encode(map[string]any{"ok": true, "balance_cc": bal})
	}
}

func roomsHandler(st *store.Store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		switch r.Method {
		case http.MethodGet:
			items, err := st.ListRooms(r.Context())
			if err != nil {
				writeHTTPError(w, http.StatusInternalServerError, "internal_error")
				return
			}
			_ = json.NewEncoder(w).Encode(map[string]any{"items": items})
		case http.MethodPost:
			var body struct {
				Name       string `json:"name"`
				MinBuyinCC int64  `json:"min_buyin_cc"`
				SmallBlind int64  `json:"small_blind_cc"`
				BigBlind   int64  `json:"big_blind_cc"`
			}
			if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
				writeHTTPError(w, http.StatusBadRequest, "invalid_json")
				return
			}
			if body.Name == "" || body.MinBuyinCC <= 0 || body.SmallBlind <= 0 || body.BigBlind <= 0 {
				writeHTTPError(w, http.StatusBadRequest, "invalid_request")
				return
			}
			id, err := st.CreateRoom(r.Context(), body.Name, body.MinBuyinCC, body.SmallBlind, body.BigBlind)
			if err != nil {
				writeHTTPError(w, http.StatusInternalServerError, "internal_error")
				return
			}
			_ = json.NewEncoder(w).Encode(map[string]any{"ok": true, "room_id": id})
		default:
			writeHTTPError(w, http.StatusMethodNotAllowed, "method_not_allowed")
		}
	}
}

func providerRatesHandler(st *store.Store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		switch r.Method {
		case http.MethodGet:
			items, err := st.ListProviderRates(r.Context())
			if err != nil {
				writeHTTPError(w, http.StatusInternalServerError, "internal_error")
				return
			}
			_ = json.NewEncoder(w).Encode(map[string]any{"items": items})
		case http.MethodPost:
			var body struct {
				Provider            string  `json:"provider"`
				PricePer1KTokensUSD float64 `json:"price_per_1k_tokens_usd"`
				CCPerUSD            float64 `json:"cc_per_usd"`
				Weight              float64 `json:"weight"`
			}
			if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
				writeHTTPError(w, http.StatusBadRequest, "invalid_json")
				return
			}
			body.Provider = strings.ToLower(strings.TrimSpace(body.Provider))
			if body.Provider == "" || body.PricePer1KTokensUSD <= 0 || body.CCPerUSD <= 0 || body.Weight <= 0 {
				writeHTTPError(w, http.StatusBadRequest, "invalid_request")
				return
			}
			if err := st.UpsertProviderRate(r.Context(), body.Provider, body.PricePer1KTokensUSD, body.CCPerUSD, body.Weight); err != nil {
				writeHTTPError(w, http.StatusInternalServerError, "internal_error")
				return
			}
			_ = json.NewEncoder(w).Encode(map[string]any{"ok": true})
		default:
			writeHTTPError(w, http.StatusMethodNotAllowed, "method_not_allowed")
		}
	}
}

func publicRoomsHandler(st *store.Store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		items, err := st.ListRooms(r.Context())
		if err != nil {
			writeHTTPError(w, http.StatusInternalServerError, "internal_error")
			return
		}
		// public subset
		out := []map[string]any{}
		for _, it := range items {
			out = append(out, map[string]any{
				"id":             it.ID,
				"name":           it.Name,
				"min_buyin_cc":   it.MinBuyinCC,
				"small_blind_cc": it.SmallBlindCC,
				"big_blind_cc":   it.BigBlindCC,
			})
		}
		_ = json.NewEncoder(w).Encode(map[string]any{"items": out})
	}
}

func publicTablesHandler(st *store.Store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		roomID := r.URL.Query().Get("room_id")
		limit, offset := parsePagination(r)
		items, err := st.ListTables(r.Context(), roomID, limit, offset)
		if err != nil {
			writeHTTPError(w, http.StatusInternalServerError, "internal_error")
			return
		}
		out := make([]map[string]any, 0, len(items))
		for _, it := range items {
			out = append(out, map[string]any{
				"table_id":       it.ID,
				"room_id":        it.RoomID,
				"status":         it.Status,
				"created_at":     it.CreatedAt,
				"small_blind_cc": it.SmallBlindCC,
				"big_blind_cc":   it.BigBlindCC,
			})
		}
		_ = json.NewEncoder(w).Encode(map[string]any{
			"items":  out,
			"limit":  limit,
			"offset": offset,
		})
	}
}

func publicTableHistoryHandler(st *store.Store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		limit, offset := parsePagination(r)
		roomID := r.URL.Query().Get("room_id")
		agentID := r.URL.Query().Get("agent_id")
		items, err := st.ListTableHistory(r.Context(), roomID, agentID, limit, offset)
		if err != nil {
			writeHTTPError(w, http.StatusInternalServerError, "internal_error")
			return
		}
		out := make([]map[string]any, 0, len(items))
		for _, it := range items {
			out = append(out, map[string]any{
				"table_id":           it.TableID,
				"room_id":            it.RoomID,
				"status":             it.Status,
				"small_blind_cc":     it.SmallBlindCC,
				"big_blind_cc":       it.BigBlindCC,
				"created_at":         it.CreatedAt,
				"last_hand_ended_at": it.LastHandEnded,
			})
		}
		_ = json.NewEncoder(w).Encode(map[string]any{
			"items":  out,
			"limit":  limit,
			"offset": offset,
		})
	}
}

func publicAgentTableHandler(coord *agentgateway.Coordinator) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		agentID := r.URL.Query().Get("agent_id")
		if agentID == "" {
			writeHTTPError(w, http.StatusBadRequest, "invalid_request")
			return
		}
		tableID, roomID, ok := coord.FindTableByAgent(agentID)
		if !ok {
			writeHTTPError(w, http.StatusNotFound, "table_not_found")
			return
		}
		_ = json.NewEncoder(w).Encode(map[string]any{
			"agent_id": agentID,
			"room_id":  roomID,
			"table_id": tableID,
		})
	}
}

func publicAgentTablesHandler(st *store.Store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		agentID := chi.URLParam(r, "agent_id")
		if agentID == "" {
			writeHTTPError(w, http.StatusBadRequest, "invalid_request")
			return
		}
		limit, offset := parsePagination(r)
		items, err := st.ListAgentTables(r.Context(), agentID, limit, offset)
		if err != nil {
			writeHTTPError(w, http.StatusInternalServerError, "internal_error")
			return
		}
		out := make([]map[string]any, 0, len(items))
		for _, it := range items {
			out = append(out, map[string]any{
				"table_id":           it.TableID,
				"room_id":            it.RoomID,
				"status":             it.Status,
				"small_blind_cc":     it.SmallBlindCC,
				"big_blind_cc":       it.BigBlindCC,
				"created_at":         it.CreatedAt,
				"last_hand_ended_at": it.LastHandEnded,
			})
		}
		_ = json.NewEncoder(w).Encode(map[string]any{
			"items":  out,
			"limit":  limit,
			"offset": offset,
		})
	}
}

func publicTableReplayHandler(st *store.Store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		start := time.Now()
		defer replayQueryP95MS.Set(time.Since(start).Milliseconds())
		replayQueryTotal.Add(1)
		tableID := chi.URLParam(r, "table_id")
		if tableID == "" {
			replayQueryErrorsTotal.Add(1)
			writeHTTPError(w, http.StatusBadRequest, "invalid_request")
			return
		}
		fromSeq := int64(1)
		if v := r.URL.Query().Get("from_seq"); v != "" {
			n, err := strconv.ParseInt(v, 10, 64)
			if err != nil || n < 1 {
				replayQueryErrorsTotal.Add(1)
				writeHTTPError(w, http.StatusBadRequest, "invalid_request")
				return
			}
			fromSeq = n
		}
		limit := 200
		if v := r.URL.Query().Get("limit"); v != "" {
			n, err := strconv.Atoi(v)
			if err != nil || n < 1 {
				replayQueryErrorsTotal.Add(1)
				writeHTTPError(w, http.StatusBadRequest, "invalid_request")
				return
			}
			limit = n
		}
		if limit > 500 {
			limit = 500
		}
		lastSeq, err := st.GetTableReplayLastSeq(r.Context(), tableID)
		if err != nil {
			replayQueryErrorsTotal.Add(1)
			writeHTTPError(w, http.StatusInternalServerError, "internal_error")
			return
		}
		if lastSeq == 0 {
			replayQueryErrorsTotal.Add(1)
			writeHTTPError(w, http.StatusNotFound, "table_not_found")
			return
		}
		items, err := st.ListTableReplayEventsFromSeq(r.Context(), tableID, fromSeq, limit)
		if err != nil {
			replayQueryErrorsTotal.Add(1)
			writeHTTPError(w, http.StatusInternalServerError, "internal_error")
			return
		}
		out := make([]map[string]any, 0, len(items))
		for _, it := range items {
			var payload any
			if len(it.Payload) > 0 {
				_ = json.Unmarshal(it.Payload, &payload)
			}
			out = append(out, map[string]any{
				"id":             it.ID,
				"table_id":       it.TableID,
				"hand_id":        it.HandID,
				"global_seq":     it.GlobalSeq,
				"hand_seq":       it.HandSeq,
				"event_type":     it.EventType,
				"actor_agent_id": it.ActorAgentID,
				"payload":        payload,
				"schema_version": it.SchemaVer,
				"created_at":     it.CreatedAt,
			})
		}
		nextFrom := fromSeq + int64(len(items))
		_ = json.NewEncoder(w).Encode(map[string]any{
			"items":         out,
			"next_from_seq": nextFrom,
			"has_more":      nextFrom <= lastSeq,
			"last_seq":      lastSeq,
		})
	}
}

func publicTableTimelineHandler(st *store.Store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		start := time.Now()
		defer replayQueryP95MS.Set(time.Since(start).Milliseconds())
		replayQueryTotal.Add(1)
		tableID := chi.URLParam(r, "table_id")
		if tableID == "" {
			replayQueryErrorsTotal.Add(1)
			writeHTTPError(w, http.StatusBadRequest, "invalid_request")
			return
		}
		hands, err := st.ListHandsByTableID(r.Context(), tableID)
		if err != nil {
			replayQueryErrorsTotal.Add(1)
			writeHTTPError(w, http.StatusInternalServerError, "internal_error")
			return
		}
		lastSeq, err := st.GetTableReplayLastSeq(r.Context(), tableID)
		if err != nil {
			replayQueryErrorsTotal.Add(1)
			writeHTTPError(w, http.StatusInternalServerError, "internal_error")
			return
		}
		if lastSeq == 0 {
			replayQueryErrorsTotal.Add(1)
			writeHTTPError(w, http.StatusNotFound, "table_not_found")
			return
		}
		events, err := st.ListTableReplayEventsFromSeq(r.Context(), tableID, 1, int(lastSeq))
		if err != nil {
			replayQueryErrorsTotal.Add(1)
			writeHTTPError(w, http.StatusInternalServerError, "internal_error")
			return
		}
		byHandSeqRange := make(map[string]map[string]int64)
		for _, ev := range events {
			if ev.HandID == "" {
				continue
			}
			rng := byHandSeqRange[ev.HandID]
			if rng == nil {
				rng = map[string]int64{"start": ev.GlobalSeq, "end": ev.GlobalSeq}
				byHandSeqRange[ev.HandID] = rng
			}
			if ev.GlobalSeq < rng["start"] {
				rng["start"] = ev.GlobalSeq
			}
			if ev.GlobalSeq > rng["end"] {
				rng["end"] = ev.GlobalSeq
			}
		}
		out := make([]map[string]any, 0, len(hands))
		for _, h := range hands {
			rng := byHandSeqRange[h.ID]
			startSeq := int64(0)
			endSeq := int64(0)
			if rng != nil {
				startSeq = rng["start"]
				endSeq = rng["end"]
			}
			out = append(out, map[string]any{
				"hand_id":         h.ID,
				"start_seq":       startSeq,
				"end_seq":         endSeq,
				"winner_agent_id": h.WinnerAgentID,
				"pot_cc":          h.PotCC,
				"street_end":      h.StreetEnd,
				"started_at":      h.StartedAt,
				"ended_at":        h.EndedAt,
			})
		}
		_ = json.NewEncoder(w).Encode(map[string]any{
			"table_id": tableID,
			"items":    out,
		})
	}
}

func publicTableSnapshotHandler(st *store.Store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		replayQueryTotal.Add(1)
		start := time.Now()
		defer replayQueryP95MS.Set(time.Since(start).Milliseconds())
		tableID := chi.URLParam(r, "table_id")
		if tableID == "" {
			replayQueryErrorsTotal.Add(1)
			writeHTTPError(w, http.StatusBadRequest, "invalid_request")
			return
		}
		atSeqRaw := r.URL.Query().Get("at_seq")
		if atSeqRaw == "" {
			replayQueryErrorsTotal.Add(1)
			writeHTTPError(w, http.StatusBadRequest, "invalid_request")
			return
		}
		atSeq, err := strconv.ParseInt(atSeqRaw, 10, 64)
		if err != nil || atSeq < 1 {
			replayQueryErrorsTotal.Add(1)
			writeHTTPError(w, http.StatusBadRequest, "invalid_request")
			return
		}
		lastSeq, err := st.GetTableReplayLastSeq(r.Context(), tableID)
		if err != nil {
			replayQueryErrorsTotal.Add(1)
			writeHTTPError(w, http.StatusInternalServerError, "internal_error")
			return
		}
		if lastSeq == 0 {
			replayQueryErrorsTotal.Add(1)
			writeHTTPError(w, http.StatusNotFound, "table_not_found")
			return
		}
		if atSeq > lastSeq {
			atSeq = lastSeq
		}
		snap, err := st.GetLatestTableReplaySnapshotAtOrBefore(r.Context(), tableID, atSeq)
		snapshotSeq := int64(0)
		replayState := map[string]any{}
		if err == nil && snap != nil {
			replaySnapshotHitTotal.Add(1)
			snapshotSeq = snap.AtGlobalSeq
			_ = json.Unmarshal(snap.StateBlob, &replayState)
		} else {
			replaySnapshotMissTotal.Add(1)
		}
		hits := replaySnapshotHitTotal.Value()
		total := hits + replaySnapshotMissTotal.Value()
		if total > 0 {
			replaySnapshotHitRatio.Set(float64(hits) / float64(total))
		}
		fromSeq := snapshotSeq + 1
		limit := int(atSeq - snapshotSeq + 1)
		if limit < 1 {
			limit = 1
		}
		events, err := st.ListTableReplayEventsFromSeq(r.Context(), tableID, fromSeq, limit)
		if err != nil {
			replayQueryErrorsTotal.Add(1)
			writeHTTPError(w, http.StatusInternalServerError, "internal_error")
			return
		}
		for _, ev := range events {
			if ev.GlobalSeq > atSeq {
				break
			}
			var payload map[string]any
			if err := json.Unmarshal(ev.Payload, &payload); err != nil {
				continue
			}
			if ev.EventType == "state_snapshot" {
				replayState = payload
			}
			replayState["last_event_type"] = ev.EventType
			replayState["global_seq"] = ev.GlobalSeq
		}
		replaySnapshotRebuildMS.Set(time.Since(start).Milliseconds())
		_ = json.NewEncoder(w).Encode(map[string]any{
			"table_id": tableID,
			"at_seq":   atSeq,
			"state":    replayState,
		})
	}
}

func publicLeaderboardHandler(st *store.Store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		limit, offset := parsePagination(r)
		items, err := st.ListLeaderboard(r.Context(), limit, offset)
		if err != nil {
			writeHTTPError(w, http.StatusInternalServerError, "internal_error")
			return
		}
		out := make([]map[string]any, 0, len(items))
		for _, it := range items {
			out = append(out, map[string]any{
				"agent_id": it.AgentID,
				"name":     it.Name,
				"net_cc":   it.NetCC,
			})
		}
		_ = json.NewEncoder(w).Encode(map[string]any{
			"items":  out,
			"limit":  limit,
			"offset": offset,
		})
	}
}

func registerAgentHandler(st *store.Store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			writeHTTPError(w, http.StatusMethodNotAllowed, "method_not_allowed")
			return
		}
		var body struct {
			Name        string `json:"name"`
			Description string `json:"description"`
		}
		if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
			writeHTTPError(w, http.StatusBadRequest, "invalid_json")
			return
		}
		if body.Name == "" {
			writeHTTPError(w, http.StatusBadRequest, "invalid_request")
			return
		}
		apiKey := "apa_" + strconv.FormatInt(time.Now().UnixNano(), 10)
		claimCode := "apa_claim_" + strconv.FormatInt(time.Now().UnixNano(), 10)
		id, err := st.CreateAgent(r.Context(), body.Name, apiKey, claimCode)
		if err != nil {
			writeHTTPError(w, http.StatusInternalServerError, "internal_error")
			return
		}
		_ = st.EnsureAccount(r.Context(), id, 10000)
		// claimURL := "https://apa.network/claim/" + claimCode
		claimURL := "http://localhost:8080/claim/" + claimCode
		_ = json.NewEncoder(w).Encode(map[string]any{
			"agent": map[string]any{
				"agent_id":          id,
				"api_key":           apiKey,
				"claim_url":         claimURL,
				"verification_code": claimCode,
			},
		})
	}
}

func agentMeHandler(st *store.Store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		agent := r.Context().Value(agentContextKey{}).(*store.Agent)
		balance, err := st.GetAccountBalance(r.Context(), agent.ID)
		if err != nil {
			writeHTTPError(w, http.StatusInternalServerError, "internal_error")
			return
		}
		_ = json.NewEncoder(w).Encode(map[string]any{
			"agent_id":   agent.ID,
			"name":       agent.Name,
			"status":     agent.Status,
			"balance_cc": balance,
			"created_at": agent.CreatedAt,
		})
	}
}

func claimAgentHandler(st *store.Store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			writeHTTPError(w, http.StatusMethodNotAllowed, "method_not_allowed")
			return
		}
		var body struct {
			AgentID   string `json:"agent_id"`
			ClaimCode string `json:"claim_code"`
		}
		if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
			writeHTTPError(w, http.StatusBadRequest, "invalid_json")
			return
		}
		claim, err := st.GetAgentClaimByAgent(r.Context(), body.AgentID)
		if err != nil || claim.ClaimCode != body.ClaimCode {
			writeHTTPError(w, http.StatusUnauthorized, "invalid_claim")
			return
		}
		if err := st.MarkAgentClaimed(r.Context(), body.AgentID); err != nil {
			writeHTTPError(w, http.StatusInternalServerError, "internal_error")
			return
		}
		_ = json.NewEncoder(w).Encode(map[string]any{"ok": true})
	}
}

func claimByCodeHandler(st *store.Store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		claimCode := chi.URLParam(r, "claim_code")
		if claimCode == "" {
			writeHTTPError(w, http.StatusBadRequest, "invalid_request")
			return
		}
		claim, err := st.GetAgentClaimByCode(r.Context(), claimCode)
		if err != nil {
			writeHTTPError(w, http.StatusNotFound, "claim_not_found")
			return
		}
		if claim.Status != "claimed" {
			if err := st.MarkAgentClaimed(r.Context(), claim.AgentID); err != nil {
				writeHTTPError(w, http.StatusInternalServerError, "internal_error")
				return
			}
			claim.Status = "claimed"
		}
		_ = json.NewEncoder(w).Encode(map[string]any{
			"ok":       true,
			"agent_id": claim.AgentID,
			"status":   claim.Status,
		})
	}
}

func bindKeyHandler(st *store.Store, cfg config.ServerConfig) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			writeHTTPError(w, http.StatusMethodNotAllowed, "method_not_allowed")
			return
		}
		var body struct {
			Provider  string  `json:"provider"`
			APIKey    string  `json:"api_key"`
			BudgetUSD float64 `json:"budget_usd"`
		}
		if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
			writeHTTPError(w, http.StatusBadRequest, "invalid_json")
			return
		}
		agent := r.Context().Value(agentContextKey{}).(*store.Agent)
		body.Provider = strings.ToLower(strings.TrimSpace(body.Provider))
		if body.Provider == "" || body.APIKey == "" || body.BudgetUSD <= 0 {
			writeHTTPError(w, http.StatusBadRequest, "invalid_request")
			return
		}
		if body.BudgetUSD > cfg.MaxBudgetUSD {
			writeHTTPError(w, http.StatusBadRequest, "budget_exceeds_limit")
			return
		}
		if body.Provider != "openai" && body.Provider != "kimi" {
			writeHTTPError(w, http.StatusBadRequest, "invalid_provider")
			return
		}

		if blocked, reason, err := st.IsAgentBlacklisted(r.Context(), agent.ID); err != nil {
			writeHTTPError(w, http.StatusInternalServerError, "internal_error")
			return
		} else if blocked {
			w.WriteHeader(http.StatusForbidden)
			_ = json.NewEncoder(w).Encode(map[string]any{"error": "agent_blacklisted", "reason": reason})
			return
		}

		if last, err := st.LastSuccessfulKeyBindAt(r.Context(), agent.ID); err != nil {
			writeHTTPError(w, http.StatusInternalServerError, "internal_error")
			return
		} else if last != nil {
			cooldown := time.Duration(cfg.BindCooldownMins) * time.Minute
			if time.Since(*last) < cooldown {
				writeHTTPError(w, http.StatusTooManyRequests, "cooldown_active")
				return
			}
		}

		keyHash := store.HashAPIKey(body.APIKey)
		if existing, err := st.GetAgentKeyByHash(r.Context(), keyHash); err == nil && existing != nil {
			writeHTTPError(w, http.StatusConflict, "api_key_already_bound")
			return
		} else if err != nil && err != store.ErrNotFound {
			writeHTTPError(w, http.StatusInternalServerError, "internal_error")
			return
		}

		if !cfg.AllowAnyVendorKey {
			if err := verifyVendorKey(r.Context(), cfg, body.Provider, body.APIKey); err != nil {
				_ = st.RecordAgentKeyAttempt(r.Context(), agent.ID, body.Provider, "invalid_key")
				if n, err := st.CountConsecutiveInvalidKeyAttempts(r.Context(), agent.ID); err == nil && n >= 3 {
					_ = st.BlacklistAgent(r.Context(), agent.ID, "too_many_invalid_keys")
					w.WriteHeader(http.StatusForbidden)
					_ = json.NewEncoder(w).Encode(map[string]any{"error": "agent_blacklisted"})
					return
				}
				writeHTTPError(w, http.StatusUnauthorized, "invalid_vendor_key")
				return
			}
		}

		rate, err := st.GetProviderRate(r.Context(), body.Provider)
		if err != nil {
			writeHTTPError(w, http.StatusBadRequest, "invalid_provider")
			return
		}
		credit := store.ComputeCCFromBudgetUSD(body.BudgetUSD, rate.CCPerUSD, rate.Weight)
		if credit <= 0 {
			writeHTTPError(w, http.StatusBadRequest, "invalid_request")
			return
		}

		keyID, err := st.CreateAgentKey(r.Context(), agent.ID, body.Provider, keyHash)
		if err != nil {
			writeHTTPError(w, http.StatusConflict, "api_key_already_bound")
			return
		}
		_ = st.RecordAgentKeyAttempt(r.Context(), agent.ID, body.Provider, "success")
		_ = st.EnsureAccount(r.Context(), agent.ID, 0)
		newBal, err := st.Credit(r.Context(), agent.ID, credit, "key_credit", "agent_key", keyID)
		if err != nil {
			writeHTTPError(w, http.StatusInternalServerError, "internal_error")
			return
		}
		_ = json.NewEncoder(w).Encode(map[string]any{
			"ok":         true,
			"added_cc":   credit,
			"balance_cc": newBal,
		})
	}
}

type agentContextKey struct{}

func agentAuthMiddleware(st *store.Store) func(http.Handler) http.Handler {
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			auth := r.Header.Get("Authorization")
			prefix := "Bearer "
			if len(auth) <= len(prefix) || auth[:len(prefix)] != prefix {
				w.WriteHeader(http.StatusUnauthorized)
				return
			}
			apiKey := auth[len(prefix):]
			agent, err := st.GetAgentByAPIKey(r.Context(), apiKey)
			if err != nil {
				w.WriteHeader(http.StatusUnauthorized)
				return
			}
			ctx := context.WithValue(r.Context(), agentContextKey{}, agent)
			next.ServeHTTP(w, r.WithContext(ctx))
		})
	}
}

func verifyVendorKey(ctx context.Context, cfg config.ServerConfig, provider, apiKey string) error {
	base := cfg.OpenAIBaseURL
	if provider == "kimi" {
		base = cfg.KimiBaseURL
	}
	client := &http.Client{Timeout: 10 * time.Second}
	url := strings.TrimRight(base, "/") + "/models"
	for attempt := 0; attempt < 2; attempt++ {
		req, err := http.NewRequestWithContext(ctx, http.MethodGet, url, nil)
		if err != nil {
			return err
		}
		req.Header.Set("Authorization", "Bearer "+apiKey)
		resp, err := client.Do(req)
		if err != nil {
			if attempt == 0 && ctx.Err() == nil {
				time.Sleep(200 * time.Millisecond)
				continue
			}
			return err
		}
		resp.Body.Close()
		if resp.StatusCode >= 500 && attempt == 0 {
			time.Sleep(200 * time.Millisecond)
			continue
		}
		if resp.StatusCode >= 400 {
			return fmt.Errorf("invalid_vendor_key")
		}
		return nil
	}
	return fmt.Errorf("invalid_vendor_key")
}

func adminAuthMiddleware(adminKey string) func(http.Handler) http.Handler {
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			if adminKey != "" {
				if !checkAdminAuth(r, adminKey) {
					w.WriteHeader(http.StatusUnauthorized)
					_ = json.NewEncoder(w).Encode(map[string]any{"ok": false, "error": "unauthorized"})
					return
				}
			}
			next.ServeHTTP(w, r)
		})
	}
}

// Backward-compatible wrappers used by legacy tests.
func withAgentAuth(st *store.Store, next http.HandlerFunc) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		agentAuthMiddleware(st)(next).ServeHTTP(w, r)
	}
}

func checkAdminAuth(r *http.Request, adminKey string) bool {
	if v := r.Header.Get("X-Admin-Key"); v == adminKey {
		return true
	}
	auth := r.Header.Get("Authorization")
	prefix := "Bearer "
	if len(auth) > len(prefix) && auth[:len(prefix)] == prefix {
		return auth[len(prefix):] == adminKey
	}
	return false
}

func parsePagination(r *http.Request) (int, int) {
	limit := 50
	offset := 0
	if v := r.URL.Query().Get("limit"); v != "" {
		if n, err := strconv.Atoi(v); err == nil {
			limit = n
		}
	}
	if v := r.URL.Query().Get("offset"); v != "" {
		if n, err := strconv.Atoi(v); err == nil {
			offset = n
		}
	}
	if limit < 1 {
		limit = 1
	}
	if limit > 500 {
		limit = 500
	}
	if offset < 0 {
		offset = 0
	}
	return limit, offset
}
