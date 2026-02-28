package runtime

import (
	"errors"
	"silicon-casino/internal/store"
)

func (c *Coordinator) GetSessionBuffer(sessionID string) *EventBuffer {
	c.mu.Lock()
	defer c.mu.Unlock()
	sess := c.sessions[sessionID]
	if sess == nil {
		return nil
	}
	return sess.buffer
}

func (c *Coordinator) Store() *store.Store {
	return c.store
}

func IsSessionNotFound(err error) bool {
	return errors.Is(err, errSessionNotFound)
}
