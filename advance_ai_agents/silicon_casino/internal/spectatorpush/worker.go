package spectatorpush

import (
	"context"
	"errors"
	"time"

	"silicon-casino/internal/spectatorpush/platforms"
)

var errCircuitOpen = errors.New("circuit_open")

type panelMessageCleaner interface {
	ForgetPanel(endpoint, panelKey string)
}

func (m *Manager) worker(ctx context.Context) {
	for {
		select {
		case <-ctx.Done():
			return
		case <-m.done:
			return
		case job := <-m.dispatchCh:
			metricPushQueueLen.Set(int64(len(m.dispatchCh)))
			m.processJob(ctx, job)
		}
	}
}

func (m *Manager) processJob(ctx context.Context, job pushJob) {
	adapter := m.adapters[job.Target.Platform]
	if adapter == nil {
		metricPushDroppedTotal.Add(1)
		return
	}

	now := time.Now()
	if err := m.beforeSend(job.key(), now); err != nil {
		metricPushCircuitOpenTotal.Add(1)
		if willRetry := m.retryOrDrop(job, err); !willRetry {
			m.markPanelDeliveryDropped(job)
		}
		return
	}

	err := adapter.Send(ctx, job.Target.Endpoint, job.Target.Secret, toPlatformMessage(job.Formatted))
	if err != nil {
		metricPushFailedTotal.Add(1)
		m.afterFailure(job.key(), time.Now())
		if willRetry := m.retryOrDrop(job, err); !willRetry {
			m.markPanelDeliveryDropped(job)
		}
		return
	}

	metricPushSentTotal.Add(1)
	m.afterSuccess(job.key())
	m.markPanelDeliverySuccess(job)
	if job.PanelTerminal {
		if cleaner, ok := adapter.(panelMessageCleaner); ok {
			cleaner.ForgetPanel(job.Target.Endpoint, job.Formatted.PanelKey)
		}
	}
}

func (m *Manager) retryOrDrop(job pushJob, _ error) bool {
	if job.Attempt >= m.cfg.RetryMax {
		metricPushRetryDroppedTotal.Add(1)
		return false
	}
	job.Attempt++
	metricPushRetryTotal.Add(1)
	delay := m.cfg.RetryBase * time.Duration(1<<(job.Attempt-1))
	m.retryQ.Enqueue(job, delay)
	return true
}

func (m *Manager) beforeSend(key string, now time.Time) error {
	m.mu.Lock()
	defer m.mu.Unlock()
	state := m.breakerByKey[key]
	if !state.openUntil.IsZero() && now.Before(state.openUntil) {
		return errCircuitOpen
	}
	return nil
}

func (m *Manager) afterFailure(key string, now time.Time) {
	m.mu.Lock()
	defer m.mu.Unlock()
	state := m.breakerByKey[key]
	state.consecutiveFailures++
	if state.consecutiveFailures >= m.cfg.FailureThreshold {
		state.openUntil = now.Add(m.cfg.CircuitOpenDuration)
		state.consecutiveFailures = 0
	}
	m.breakerByKey[key] = state
}

func (m *Manager) afterSuccess(key string) {
	m.mu.Lock()
	defer m.mu.Unlock()
	m.breakerByKey[key] = breakerState{}
}

func toPlatformMessage(msg FormattedMessage) platforms.Message {
	fields := make([]platforms.Field, 0, len(msg.Fields))
	for _, f := range msg.Fields {
		fields = append(fields, platforms.Field{Name: f.Name, Value: f.Value, Inline: f.Inline})
	}
	return platforms.Message{
		PanelKey:    msg.PanelKey,
		Title:       msg.Title,
		Content:     msg.Content,
		Description: msg.Description,
		Color:       msg.Color,
		Timestamp:   msg.Timestamp,
		Footer:      msg.Footer,
		Fields:      fields,
	}
}
