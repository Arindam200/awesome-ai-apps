package agentgateway

import (
	"net/http"

	agstream "silicon-casino/internal/agentgateway/stream"
)

// SetSSEHeaders applies headers that keep event streams stable across proxies.
func SetSSEHeaders(w http.ResponseWriter) {
	agstream.SetSSEHeaders(w)
}
