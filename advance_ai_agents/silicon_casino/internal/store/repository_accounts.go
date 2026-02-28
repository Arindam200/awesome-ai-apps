package store

import (
	"context"
	"errors"

	"silicon-casino/internal/store/sqlcgen"

	"github.com/jackc/pgx/v5"
)

func (s *Store) GetAccountBalance(ctx context.Context, agentID string) (int64, error) {
	bal, err := s.q.GetAccountBalanceByAgentID(ctx, agentID)
	if err != nil {
		return 0, mapNotFound(err)
	}
	return bal, nil
}
func (s *Store) Debit(ctx context.Context, agentID string, amount int64, entryType, refType, refID string) (int64, error) {
	if amount < 0 {
		return 0, errors.New("amount must be positive")
	}
	tx, err := s.Pool.BeginTx(ctx, pgx.TxOptions{})
	if err != nil {
		return 0, err
	}
	defer tx.Rollback(ctx)

	qtx := s.q.WithTx(tx)
	bal, err := qtx.GetAccountBalanceByAgentIDForUpdate(ctx, agentID)
	if err != nil {
		return 0, mapNotFound(err)
	}
	if bal < amount {
		return 0, errors.New("insufficient_balance")
	}
	newBal := bal - amount
	if err := qtx.UpdateAccountBalance(ctx, sqlcgen.UpdateAccountBalanceParams{
		BalanceCc: newBal,
		ID:        agentID,
	}); err != nil {
		return 0, err
	}
	if err := qtx.InsertLedgerEntry(ctx, sqlcgen.InsertLedgerEntryParams{
		ID:       NewID(),
		AgentID:  agentID,
		Type:     entryType,
		AmountCc: -amount,
		RefType:  refType,
		RefID:    refID,
	}); err != nil {
		return 0, err
	}
	if err := tx.Commit(ctx); err != nil {
		return 0, err
	}
	return newBal, nil
}

func (s *Store) Credit(ctx context.Context, agentID string, amount int64, entryType, refType, refID string) (int64, error) {
	if amount < 0 {
		return 0, errors.New("amount must be positive")
	}
	tx, err := s.Pool.BeginTx(ctx, pgx.TxOptions{})
	if err != nil {
		return 0, err
	}
	defer tx.Rollback(ctx)

	qtx := s.q.WithTx(tx)
	bal, err := qtx.GetAccountBalanceByAgentIDForUpdate(ctx, agentID)
	if err != nil {
		return 0, mapNotFound(err)
	}
	newBal := bal + amount
	if err := qtx.UpdateAccountBalance(ctx, sqlcgen.UpdateAccountBalanceParams{
		BalanceCc: newBal,
		ID:        agentID,
	}); err != nil {
		return 0, err
	}
	if err := qtx.InsertLedgerEntry(ctx, sqlcgen.InsertLedgerEntryParams{
		ID:       NewID(),
		AgentID:  agentID,
		Type:     entryType,
		AmountCc: amount,
		RefType:  refType,
		RefID:    refID,
	}); err != nil {
		return 0, err
	}
	if err := tx.Commit(ctx); err != nil {
		return 0, err
	}
	return newBal, nil
}

func (s *Store) EnsureAccount(ctx context.Context, agentID string, initial int64) error {
	return s.q.EnsureAccount(ctx, sqlcgen.EnsureAccountParams{
		ID:        agentID,
		BalanceCc: initial,
	})
}
func (s *Store) ListAccounts(ctx context.Context, agentID string, limit, offset int) ([]Account, error) {
	if limit <= 0 {
		limit = 50
	}
	rows, err := s.q.ListAccounts(ctx, sqlcgen.ListAccountsParams{
		AgentID:    agentID,
		LimitRows:  int32(limit),
		OffsetRows: int32(offset),
	})
	if err != nil {
		return nil, err
	}
	out := make([]Account, 0, len(rows))
	for _, r := range rows {
		out = append(out, Account{
			AgentID:   r.AgentID,
			BalanceCC: r.BalanceCc,
			UpdatedAt: r.UpdatedAt.Time,
		})
	}
	return out, nil
}
