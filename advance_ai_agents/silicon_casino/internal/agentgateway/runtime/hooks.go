package runtime

type TableMeta struct {
	TableID string
	RoomID  string
}

type TableLifecycleObserver interface {
	OnTableStarted(meta TableMeta, buf *EventBuffer)
	OnTableClosed(tableID string)
}

func (c *Coordinator) SetTableLifecycleObserver(obs TableLifecycleObserver) {
	c.mu.Lock()
	defer c.mu.Unlock()
	c.tableObserver = obs
}
