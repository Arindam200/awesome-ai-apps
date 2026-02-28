package agentgateway

import (
	"net/http"

	agstream "silicon-casino/internal/agentgateway/stream"
)

func WriteSSE(w http.ResponseWriter, ev StreamEvent) error {
	return agstream.WriteSSE(w, ev)
}
