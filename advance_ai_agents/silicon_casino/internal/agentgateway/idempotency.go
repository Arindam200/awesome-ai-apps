package agentgateway

import (
	"context"

	"silicon-casino/internal/store"
)

func (c *Coordinator) saveActionResult(ctx context.Context, sessionID string, req ActionRequest, res ActionResponse) (bool, error) {
	rec := store.AgentActionRequest{
		SessionID:  sessionID,
		RequestID:  req.RequestID,
		TurnID:     req.TurnID,
		Action:     req.Action,
		AmountCC:   req.Amount,
		ThoughtLog: req.ThoughtLog,
		Accepted:   res.Accepted,
		Reason:     res.Reason,
	}
	return c.store.InsertAgentActionRequest(ctx, rec)
}

func (c *Coordinator) getIdempotentActionResult(ctx context.Context, sessionID, requestID string) (*ActionResponse, error) {
	rec, err := c.store.GetAgentActionRequest(ctx, sessionID, requestID)
	if err != nil {
		if err == store.ErrNotFound {
			return nil, nil
		}
		return nil, err
	}
	return &ActionResponse{
		Accepted:  rec.Accepted,
		RequestID: rec.RequestID,
		Reason:    rec.Reason,
	}, nil
}
