package agentgateway

import (
	"time"

	"silicon-casino/internal/agentgateway/runtime"
	"silicon-casino/internal/ledger"
	"silicon-casino/internal/store"
)

type Coordinator = runtime.Coordinator

type CreateSessionRequest = runtime.CreateSessionRequest
type CreateSessionResponse = runtime.CreateSessionResponse
type ActionRequest = runtime.ActionRequest
type ActionResponse = runtime.ActionResponse
type ErrorResponse = runtime.ErrorResponse

type TableMeta = runtime.TableMeta
type TableLifecycleObserver = runtime.TableLifecycleObserver

func NewCoordinator(st *store.Store, led *ledger.Ledger) *Coordinator {
	return runtime.NewCoordinator(st, led)
}

func MapSessionCreateError(err error) (int, string) {
	return runtime.MapSessionCreateError(err)
}

func MapActionSubmitError(err error) (int, string) {
	return runtime.MapActionSubmitError(err)
}

func IsSessionNotFound(err error) bool {
	return runtime.IsSessionNotFound(err)
}

func SetReconnectGracePeriodForTest(d time.Duration) {
	runtime.SetReconnectGracePeriodForTest(d)
}

func ReconnectGracePeriod() time.Duration {
	return runtime.ReconnectGracePeriod()
}
