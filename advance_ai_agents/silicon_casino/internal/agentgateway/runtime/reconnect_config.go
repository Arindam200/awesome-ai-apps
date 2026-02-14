package runtime

import "time"

func SetReconnectGracePeriodForTest(d time.Duration) {
	reconnectGracePeriod = d
}

func ReconnectGracePeriod() time.Duration {
	return reconnectGracePeriod
}
