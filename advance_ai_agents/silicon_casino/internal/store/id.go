package store

import (
	"math/rand"
	"sync"
	"time"

	"github.com/oklog/ulid/v2"
)

var (
	ulidEntropy   = ulid.Monotonic(rand.New(rand.NewSource(time.Now().UnixNano())), 0)
	ulidEntropyMu sync.Mutex
)

func NewID() string {
	ulidEntropyMu.Lock()
	defer ulidEntropyMu.Unlock()
	return ulid.MustNew(ulid.Timestamp(time.Now()), ulidEntropy).String()
}
