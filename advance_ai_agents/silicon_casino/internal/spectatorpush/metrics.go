package spectatorpush

import "expvar"

var (
	metricPushQueuedTotal       = expvar.NewInt("spectator_push_queued_total")
	metricPushDroppedTotal      = expvar.NewInt("spectator_push_dropped_total")
	metricPushRetryTotal        = expvar.NewInt("spectator_push_retry_total")
	metricPushRetryDroppedTotal = expvar.NewInt("spectator_push_retry_dropped_total")
	metricPushSentTotal         = expvar.NewInt("spectator_push_sent_total")
	metricPushFailedTotal       = expvar.NewInt("spectator_push_failed_total")
	metricPushCircuitOpenTotal  = expvar.NewInt("spectator_push_circuit_open_total")
	metricPushQueueLen          = expvar.NewInt("spectator_push_queue_len")
	metricPushConfigReloadTotal = expvar.NewInt("spectator_push_config_reload_total")
	metricPushConfigReloadError = expvar.NewInt("spectator_push_config_reload_error_total")
)
