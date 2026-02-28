package main

import (
	"context"
	"net/http"
	"time"

	"silicon-casino/internal/agentgateway"
	"silicon-casino/internal/config"
	"silicon-casino/internal/ledger"
	"silicon-casino/internal/logging"
	"silicon-casino/internal/spectatorpush"
	"silicon-casino/internal/store"

	"github.com/rs/zerolog/log"
)

const (
	defaultOpenRouterPricePer1KUSD = 0.0001
	defaultNebiusPricePer1KUSD     = 0.0001
	defaultProviderWeight          = 1.0
)

func main() {
	logCfg, err := config.LoadLog()
	if err != nil {
		log.Fatal().Err(err).Msg("load log config failed")
	}
	logging.Init(logCfg)
	cfg, err := config.LoadServer()
	if err != nil {
		log.Fatal().Err(err).Msg("load server config failed")
	}

	st, err := store.New(cfg.PostgresDSN)
	if err != nil {
		log.Fatal().Err(err).Msg("store init failed")
	}
	if err := st.Ping(context.Background()); err != nil {
		log.Fatal().Err(err).Msg("db ping failed")
	}

	led := ledger.New(st)
	if err := st.EnsureDefaultRooms(context.Background()); err != nil {
		log.Fatal().Err(err).Msg("ensure default rooms failed")
	}
	if err := st.EnsureDefaultProviderRates(context.Background(), defaultProviderRates(cfg)); err != nil {
		log.Fatal().Err(err).Msg("ensure provider rates failed")
	}
	agentCoord := agentgateway.NewCoordinator(st, led)
	pushCfg, err := spectatorpush.ConfigFromServer(cfg)
	if err != nil {
		log.Fatal().Err(err).Msg("load spectator push config failed")
	}
	pushManager := spectatorpush.NewManager(pushCfg)
	agentCoord.SetTableLifecycleObserver(pushManager)
	if err := pushManager.Start(context.Background()); err != nil {
		log.Fatal().Err(err).Msg("start spectator push manager failed")
	}
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

func defaultProviderRates(cfg config.ServerConfig) []store.ProviderRate {
	ccPerUSD := cfg.CCPerUSD
	return []store.ProviderRate{
		{
			Provider:            "openrouter",
			PricePer1KTokensUSD: defaultOpenRouterPricePer1KUSD,
			CCPerUSD:            ccPerUSD,
			Weight:              defaultProviderWeight,
		},
		{
			Provider:            "nebius",
			PricePer1KTokensUSD: defaultNebiusPricePer1KUSD,
			CCPerUSD:            ccPerUSD,
			Weight:              defaultProviderWeight,
		},
	}
}
