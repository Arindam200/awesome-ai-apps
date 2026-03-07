package ledger

import (
	"context"

	"silicon-casino/internal/store"
)

type Ledger struct {
	Store *store.Store
}

func New(s *store.Store) *Ledger {
	return &Ledger{Store: s}
}

func (l *Ledger) DebitBlind(ctx context.Context, agentID, handID string, amount int64) (int64, error) {
	return l.Store.Debit(ctx, agentID, amount, "blind_debit", "hand", handID)
}

func (l *Ledger) CreditPot(ctx context.Context, agentID, handID string, amount int64) (int64, error) {
	return l.Store.Credit(ctx, agentID, amount, "pot_credit", "hand", handID)
}
