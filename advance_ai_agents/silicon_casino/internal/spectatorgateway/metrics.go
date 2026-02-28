package spectatorgateway

import "expvar"

var (
	metricSpectatorSSEConnectionsTotal  = expvar.NewInt("spectator_sse_connections_total")
	metricSpectatorSSEConnectionsActive = expvar.NewInt("spectator_sse_connections_active")
)
