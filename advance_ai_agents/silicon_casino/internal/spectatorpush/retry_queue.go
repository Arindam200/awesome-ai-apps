package spectatorpush

import "time"

type retryQueue struct {
	out  chan<- pushJob
	done <-chan struct{}
}

func newRetryQueue(out chan<- pushJob, done <-chan struct{}) *retryQueue {
	return &retryQueue{out: out, done: done}
}

func (q *retryQueue) Enqueue(job pushJob, delay time.Duration) {
	if delay < 0 {
		delay = 0
	}
	time.AfterFunc(delay, func() {
		select {
		case <-q.done:
			return
		case q.out <- job:
			metricPushQueueLen.Set(int64(len(q.out)))
		}
	})
}
