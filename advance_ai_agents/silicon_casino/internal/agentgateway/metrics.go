package agentgateway

import "expvar"

var (
	metricSessionCreateTotal  = expvar.NewInt("session_create_total")
	metricSessionCreateErrors = expvar.NewInt("session_create_errors_total")

	metricActionSubmitTotal  = expvar.NewInt("action_submit_total")
	metricActionSubmitErrors = expvar.NewInt("action_submit_errors_total")

	metricAgentSSEConnectionsTotal  = expvar.NewInt("agent_sse_connections_total")
	metricAgentSSEConnectionsActive = expvar.NewInt("agent_sse_connections_active")
)
