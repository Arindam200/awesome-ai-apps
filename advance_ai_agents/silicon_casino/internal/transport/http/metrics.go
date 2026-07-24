package httptransport

import "expvar"

var (
	metricSessionCreateTotal  = expvar.NewInt("session_create_total")
	metricSessionCreateErrors = expvar.NewInt("session_create_errors_total")

	metricActionSubmitTotal  = expvar.NewInt("action_submit_total")
	metricActionSubmitErrors = expvar.NewInt("action_submit_errors_total")

	metricAgentSSEConnectionsTotal  = expvar.NewInt("agent_sse_connections_total")
	metricAgentSSEConnectionsActive = expvar.NewInt("agent_sse_connections_active")

	replayQueryTotal        = expvar.NewInt("replay_query_total")
	replayQueryErrorsTotal  = expvar.NewInt("replay_query_errors_total")
	replayQueryP95MS        = expvar.NewInt("replay_query_p95_ms")
	replaySnapshotRebuildMS = expvar.NewInt("replay_snapshot_rebuild_ms")
	replaySnapshotHitTotal  = expvar.NewInt("replay_snapshot_hit_total")
	replaySnapshotMissTotal = expvar.NewInt("replay_snapshot_miss_total")
	replaySnapshotHitRatio  = expvar.NewFloat("replay_snapshot_hit_ratio")
)
