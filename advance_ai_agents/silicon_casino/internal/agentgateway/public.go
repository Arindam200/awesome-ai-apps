package agentgateway

import (
	"errors"

	"silicon-casino/internal/game/viewmodel"
)

func (c *Coordinator) GetPublicState(tableID string) (viewmodel.PublicStateView, error) {
	c.mu.Lock()
	rt := c.tables[tableID]
	c.mu.Unlock()
	if rt == nil {
		return viewmodel.PublicStateView{}, errors.New("table_not_found")
	}
	rt.mu.Lock()
	defer rt.mu.Unlock()
	state := viewmodel.BuildPublicState(rt.engine.State)
	state.TableStatus = rt.status
	state.ReconnectDeadlineTS = rt.reconnectDeadline.UnixMilli()
	state.CloseReason = rt.closeReason
	return state, nil
}

func (c *Coordinator) GetPublicBuffer(tableID, roomID string) (*EventBuffer, error) {
	c.mu.Lock()
	defer c.mu.Unlock()
	if tableID != "" {
		rt := c.tables[tableID]
		if rt == nil {
			return nil, errors.New("table_not_found")
		}
		return rt.publicBuffer, nil
	}
	if roomID != "" {
		for _, rt := range c.tables {
			if rt.room != nil && rt.room.ID == roomID {
				return rt.publicBuffer, nil
			}
		}
		return nil, errors.New("table_not_found")
	}
	for _, rt := range c.tables {
		return rt.publicBuffer, nil
	}
	return nil, errors.New("table_not_found")
}
