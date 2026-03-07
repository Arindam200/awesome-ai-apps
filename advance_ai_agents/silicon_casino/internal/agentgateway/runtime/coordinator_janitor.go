package runtime

import (
	"context"
	"time"
)

func (c *Coordinator) StartJanitor(ctx context.Context, interval time.Duration) {
	if interval <= 0 {
		interval = time.Minute
	}
	expiryTicker := time.NewTicker(interval)
	sweepTicker := time.NewTicker(coordinatorSweepInterval)
	go func() {
		defer expiryTicker.Stop()
		defer sweepTicker.Stop()
		for {
			select {
			case <-ctx.Done():
				return
			case now := <-expiryTicker.C:
				_ = c.expireSessions(ctx, now)
			case now := <-sweepTicker.C:
				c.sweepTableTransitions(ctx, now)
			}
		}
	}()
}
