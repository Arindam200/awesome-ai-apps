package main

import (
	"silicon-casino/internal/agentgateway"
	"silicon-casino/internal/config"
	"silicon-casino/internal/store"
	httptransport "silicon-casino/internal/transport/http"

	"github.com/go-chi/chi/v5"
)

func newRouter(st *store.Store, cfg config.ServerConfig, agentCoord *agentgateway.Coordinator) *chi.Mux {
	return httptransport.NewRouter(st, cfg, agentCoord)
}

func logRoutes(r chi.Router) {
	httptransport.LogRoutes(r)
}
