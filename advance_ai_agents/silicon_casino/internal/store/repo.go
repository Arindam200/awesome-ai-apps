package store

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"time"

	"silicon-casino/internal/store/sqlcgen"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgtype"
	"github.com/jackc/pgx/v5/pgxpool"
)

var ErrNotFound = errors.New("not found")

// Store wraps DB access.
type Store struct {
	Pool *pgxpool.Pool
	q    *sqlcgen.Queries
}

func New(dsn string) (*Store, error) {
	pool, err := pgxpool.New(context.Background(), dsn)
	if err != nil {
		return nil, err
	}
	return &Store{Pool: pool, q: sqlcgen.New(pool)}, nil
}

func (s *Store) Close() {
	if s.Pool != nil {
		s.Pool.Close()
	}
}

func HashAPIKey(key string) string {
	h := sha256.Sum256([]byte(key))
	return hex.EncodeToString(h[:])
}

func (s *Store) GetAgentByAPIKey(ctx context.Context, apiKey string) (*Agent, error) {
	hash := HashAPIKey(apiKey)
	row, err := s.q.GetAgentByAPIKeyHash(ctx, hash)
	if err != nil {
		return nil, mapNotFound(err)
	}
	return &Agent{
		ID:         row.ID,
		Name:       row.Name,
		APIKeyHash: row.ApiKeyHash,
		Status:     row.Status,
		ClaimCode:  row.ClaimCode,
		CreatedAt:  row.CreatedAt.Time,
	}, nil
}

func (s *Store) GetAccountBalance(ctx context.Context, agentID string) (int64, error) {
	bal, err := s.q.GetAccountBalanceByAgentID(ctx, agentID)
	if err != nil {
		return 0, mapNotFound(err)
	}
	return bal, nil
}

func (s *Store) CreateTable(ctx context.Context, roomID, status string, sb, bb int64) (string, error) {
	id := NewID()
	err := s.q.CreateTable(ctx, sqlcgen.CreateTableParams{
		ID:           id,
		RoomID:       textParam(roomID),
		Status:       status,
		SmallBlindCc: sb,
		BigBlindCc:   bb,
	})
	return id, err
}

func (s *Store) ListTables(ctx context.Context, roomID string, limit, offset int) ([]Table, error) {
	if limit <= 0 {
		limit = 50
	}
	rows, err := s.q.ListTables(ctx, sqlcgen.ListTablesParams{
		Column1: roomID,
		Limit:   int32(limit),
		Offset:  int32(offset),
	})
	if err != nil {
		return nil, err
	}
	out := make([]Table, 0, len(rows))
	for _, r := range rows {
		out = append(out, Table{
			ID:           r.ID,
			RoomID:       textVal(r.RoomID),
			Status:       r.Status,
			SmallBlindCC: r.SmallBlindCc,
			BigBlindCC:   r.BigBlindCc,
			CreatedAt:    r.CreatedAt.Time,
		})
	}
	return out, nil
}

func (s *Store) CreateHand(ctx context.Context, tableID string) (string, error) {
	id := NewID()
	err := s.q.CreateHand(ctx, sqlcgen.CreateHandParams{ID: id, TableID: tableID})
	return id, err
}

func (s *Store) EndHand(ctx context.Context, handID string) error {
	return s.q.EndHand(ctx, sqlcgen.EndHandParams{
		ID:      handID,
		Column2: "",
		PotCc:   int8PtrParam(nil),
		Column4: "",
	})
}

func (s *Store) EndHandWithSummary(ctx context.Context, handID, winnerAgentID string, potCC *int64, streetEnd string) error {
	return s.q.EndHand(ctx, sqlcgen.EndHandParams{
		ID:      handID,
		Column2: winnerAgentID,
		PotCc:   int8PtrParam(potCC),
		Column4: streetEnd,
	})
}

func (s *Store) RecordAction(ctx context.Context, handID, agentID, actionType string, amount int64) error {
	return s.q.RecordAction(ctx, sqlcgen.RecordActionParams{
		ID:         NewID(),
		HandID:     handID,
		AgentID:    agentID,
		ActionType: actionType,
		AmountCc:   amount,
	})
}

func (s *Store) RecordProxyCall(ctx context.Context, agentID, model, provider string, prompt, completion, total int, cost int64) (string, error) {
	id := NewID()
	err := s.q.RecordProxyCall(ctx, sqlcgen.RecordProxyCallParams{
		ID:               id,
		AgentID:          agentID,
		PromptTokens:     int32(prompt),
		CompletionTokens: int32(completion),
		TotalTokens:      int4Param(int32(total)),
		Model:            textParam(model),
		Provider:         textParam(provider),
		CostCc:           cost,
	})
	return id, err
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

func (s *Store) CreateAgent(ctx context.Context, name, apiKey, claimCode string) (string, error) {
	id := NewID()
	hash := HashAPIKey(apiKey)
	err := s.q.CreateAgent(ctx, sqlcgen.CreateAgentParams{
		ID:         id,
		Name:       name,
		ApiKeyHash: hash,
		ClaimCode:  claimCode,
	})
	return id, err
}

func (s *Store) Ping(ctx context.Context) error {
	ctx, cancel := context.WithTimeout(ctx, 2*time.Second)
	defer cancel()
	return s.Pool.Ping(ctx)
}

func (s *Store) ListRooms(ctx context.Context) ([]Room, error) {
	rows, err := s.q.ListRooms(ctx)
	if err != nil {
		return nil, err
	}
	out := make([]Room, 0, len(rows))
	for _, r := range rows {
		out = append(out, Room{
			ID:           r.ID,
			Name:         r.Name,
			MinBuyinCC:   r.MinBuyinCc,
			SmallBlindCC: r.SmallBlindCc,
			BigBlindCC:   r.BigBlindCc,
			Status:       r.Status,
			CreatedAt:    r.CreatedAt.Time,
		})
	}
	return out, nil
}

func (s *Store) GetRoom(ctx context.Context, id string) (*Room, error) {
	r, err := s.q.GetRoomByID(ctx, id)
	if err != nil {
		return nil, mapNotFound(err)
	}
	return &Room{
		ID:           r.ID,
		Name:         r.Name,
		MinBuyinCC:   r.MinBuyinCc,
		SmallBlindCC: r.SmallBlindCc,
		BigBlindCC:   r.BigBlindCc,
		Status:       r.Status,
		CreatedAt:    r.CreatedAt.Time,
	}, nil
}

func (s *Store) CreateRoom(ctx context.Context, name string, minBuyin, sb, bb int64) (string, error) {
	id := NewID()
	err := s.q.CreateRoom(ctx, sqlcgen.CreateRoomParams{
		ID:           id,
		Name:         name,
		MinBuyinCc:   minBuyin,
		SmallBlindCc: sb,
		BigBlindCc:   bb,
	})
	return id, err
}

func (s *Store) CountRooms(ctx context.Context) (int, error) {
	c, err := s.q.CountRooms(ctx)
	return int(c), err
}

func (s *Store) EnsureDefaultRooms(ctx context.Context) error {
	c, err := s.CountRooms(ctx)
	if err != nil {
		return err
	}
	if c > 0 {
		return nil
	}
	if _, err := s.CreateRoom(ctx, "Low", 1000, 50, 100); err != nil {
		return err
	}
	if _, err := s.CreateRoom(ctx, "Mid", 5000, 100, 200); err != nil {
		return err
	}
	_, err = s.CreateRoom(ctx, "High", 20000, 500, 1000)
	return err
}

type LedgerFilter struct {
	AgentID string
	HandID  string
	From    *time.Time
	To      *time.Time
}

func (s *Store) ListAgents(ctx context.Context, limit, offset int) ([]Agent, error) {
	if limit <= 0 {
		limit = 50
	}
	rows, err := s.q.ListAgents(ctx, sqlcgen.ListAgentsParams{
		Limit:  int32(limit),
		Offset: int32(offset),
	})
	if err != nil {
		return nil, err
	}
	out := make([]Agent, 0, len(rows))
	for _, r := range rows {
		out = append(out, Agent{
			ID:         r.ID,
			Name:       r.Name,
			APIKeyHash: r.ApiKeyHash,
			Status:     r.Status,
			ClaimCode:  r.ClaimCode,
			CreatedAt:  r.CreatedAt.Time,
		})
	}
	return out, nil
}

func (s *Store) GetAgentClaimByAgent(ctx context.Context, agentID string) (*AgentClaim, error) {
	r, err := s.q.GetAgentClaimByAgentID(ctx, agentID)
	if err != nil {
		return nil, mapNotFound(err)
	}
	return &AgentClaim{
		ID:        r.ID,
		AgentID:   r.AgentID,
		ClaimCode: r.ClaimCode,
		Status:    r.Status,
		CreatedAt: r.CreatedAt.Time,
	}, nil
}

func (s *Store) GetAgentClaimByCode(ctx context.Context, claimCode string) (*AgentClaim, error) {
	r, err := s.q.GetAgentClaimByClaimCode(ctx, claimCode)
	if err != nil {
		return nil, mapNotFound(err)
	}
	return &AgentClaim{
		ID:        r.ID,
		AgentID:   r.AgentID,
		ClaimCode: r.ClaimCode,
		Status:    r.Status,
		CreatedAt: r.CreatedAt.Time,
	}, nil
}

func (s *Store) MarkAgentClaimed(ctx context.Context, agentID string) error {
	return s.q.MarkAgentStatusClaimed(ctx, agentID)
}

func (s *Store) CreateAgentKey(ctx context.Context, agentID, provider, apiKeyHash string) (string, error) {
	id := NewID()
	err := s.q.CreateAgentKey(ctx, sqlcgen.CreateAgentKeyParams{
		ID:         id,
		AgentID:    agentID,
		Provider:   provider,
		ApiKeyHash: apiKeyHash,
	})
	return id, err
}

func (s *Store) GetAgentKeyByHash(ctx context.Context, apiKeyHash string) (*AgentKey, error) {
	r, err := s.q.GetAgentKeyByAPIKeyHash(ctx, apiKeyHash)
	if err != nil {
		return nil, mapNotFound(err)
	}
	return &AgentKey{
		ID:         r.ID,
		AgentID:    r.AgentID,
		Provider:   r.Provider,
		APIKeyHash: r.ApiKeyHash,
		Status:     r.Status,
		CreatedAt:  r.CreatedAt.Time,
	}, nil
}

func (s *Store) ListProviderRates(ctx context.Context) ([]ProviderRate, error) {
	rows, err := s.q.ListProviderRates(ctx)
	if err != nil {
		return nil, err
	}
	out := make([]ProviderRate, 0, len(rows))
	for _, r := range rows {
		out = append(out, ProviderRate{
			Provider:            r.Provider,
			PricePer1KTokensUSD: r.PricePer1kTokensUsd,
			CCPerUSD:            r.CcPerUsd,
			Weight:              r.Weight,
			UpdatedAt:           r.UpdatedAt.Time,
		})
	}
	return out, nil
}

func (s *Store) IsAgentBlacklisted(ctx context.Context, agentID string) (bool, string, error) {
	reason, err := s.q.GetAgentBlacklistReasonByAgentID(ctx, agentID)
	if err != nil {
		if errors.Is(err, pgx.ErrNoRows) {
			return false, "", nil
		}
		return false, "", err
	}
	return true, reason, nil
}

func (s *Store) BlacklistAgent(ctx context.Context, agentID, reason string) error {
	return s.q.BlacklistAgent(ctx, sqlcgen.BlacklistAgentParams{AgentID: agentID, Reason: reason})
}

func (s *Store) RecordAgentKeyAttempt(ctx context.Context, agentID, provider, status string) error {
	return s.q.RecordAgentKeyAttempt(ctx, sqlcgen.RecordAgentKeyAttemptParams{
		ID:       NewID(),
		AgentID:  agentID,
		Provider: provider,
		Status:   status,
	})
}

func (s *Store) LastSuccessfulKeyBindAt(ctx context.Context, agentID string) (*time.Time, error) {
	ts, err := s.q.GetLastSuccessfulKeyBindAtByAgentID(ctx, agentID)
	if err != nil {
		if errors.Is(err, pgx.ErrNoRows) {
			return nil, nil
		}
		return nil, err
	}
	if !ts.Valid {
		return nil, nil
	}
	t := ts.Time
	return &t, nil
}

func (s *Store) CountConsecutiveInvalidKeyAttempts(ctx context.Context, agentID string) (int, error) {
	statuses, err := s.q.ListAgentKeyAttemptStatusesByAgentID(ctx, agentID)
	if err != nil {
		return 0, err
	}
	count := 0
	for _, status := range statuses {
		if status == "success" {
			break
		}
		if status == "invalid_key" {
			count++
		}
	}
	return count, nil
}

func (s *Store) GetProviderRate(ctx context.Context, provider string) (*ProviderRate, error) {
	r, err := s.q.GetProviderRateByProvider(ctx, provider)
	if err != nil {
		return nil, mapNotFound(err)
	}
	return &ProviderRate{
		Provider:            r.Provider,
		PricePer1KTokensUSD: r.PricePer1kTokensUsd,
		CCPerUSD:            r.CcPerUsd,
		Weight:              r.Weight,
		UpdatedAt:           r.UpdatedAt.Time,
	}, nil
}

func (s *Store) UpsertProviderRate(ctx context.Context, provider string, pricePer1KTokensUSD, ccPerUSD, weight float64) error {
	return s.q.UpsertProviderRate(ctx, sqlcgen.UpsertProviderRateParams{
		Provider:            provider,
		PricePer1kTokensUsd: pricePer1KTokensUSD,
		CcPerUsd:            ccPerUSD,
		Weight:              weight,
	})
}

func (s *Store) EnsureDefaultProviderRates(ctx context.Context, defaults []ProviderRate) error {
	for _, r := range defaults {
		if err := s.q.EnsureDefaultProviderRate(ctx, sqlcgen.EnsureDefaultProviderRateParams{
			Provider:            r.Provider,
			PricePer1kTokensUsd: r.PricePer1KTokensUSD,
			CcPerUsd:            r.CCPerUSD,
			Weight:              r.Weight,
		}); err != nil {
			return err
		}
	}
	return nil
}

func (s *Store) ListAccounts(ctx context.Context, agentID string, limit, offset int) ([]Account, error) {
	if limit <= 0 {
		limit = 50
	}
	rows, err := s.q.ListAccounts(ctx, sqlcgen.ListAccountsParams{
		Column1: agentID,
		Limit:   int32(limit),
		Offset:  int32(offset),
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

func (s *Store) ListLedgerEntries(ctx context.Context, f LedgerFilter, limit, offset int) ([]LedgerEntry, error) {
	if limit <= 0 {
		limit = 50
	}
	rows, err := s.q.ListLedgerEntries(ctx, sqlcgen.ListLedgerEntriesParams{
		Column1: f.AgentID,
		Column2: f.HandID,
		Column3: timeParam(f.From),
		Column4: timeParam(f.To),
		Limit:   int32(limit),
		Offset:  int32(offset),
	})
	if err != nil {
		return nil, err
	}
	out := make([]LedgerEntry, 0, len(rows))
	for _, r := range rows {
		out = append(out, LedgerEntry{
			ID:        r.ID,
			AgentID:   r.AgentID,
			Type:      r.Type,
			AmountCC:  r.AmountCc,
			RefType:   r.RefType,
			RefID:     r.RefID,
			CreatedAt: r.CreatedAt.Time,
		})
	}
	return out, nil
}

func (s *Store) ListLeaderboard(ctx context.Context, limit, offset int) ([]LeaderboardEntry, error) {
	if limit <= 0 {
		limit = 50
	}
	rows, err := s.q.ListLeaderboard(ctx, sqlcgen.ListLeaderboardParams{
		Limit:  int32(limit),
		Offset: int32(offset),
	})
	if err != nil {
		return nil, err
	}
	out := make([]LeaderboardEntry, 0, len(rows))
	for _, r := range rows {
		out = append(out, LeaderboardEntry{
			AgentID: r.ID,
			Name:    r.Name,
			NetCC:   anyToInt64(r.NetCc),
		})
	}
	return out, nil
}

func mapNotFound(err error) error {
	if errors.Is(err, pgx.ErrNoRows) {
		return ErrNotFound
	}
	return err
}

func textParam(v string) pgtype.Text {
	if v == "" {
		return pgtype.Text{}
	}
	return pgtype.Text{String: v, Valid: true}
}

func int4Param(v int32) pgtype.Int4 {
	return pgtype.Int4{Int32: v, Valid: true}
}

func timestamptzParam(v time.Time) pgtype.Timestamptz {
	return pgtype.Timestamptz{Time: v, Valid: true}
}

func int4PtrParam(v *int) pgtype.Int4 {
	if v == nil {
		return pgtype.Int4{}
	}
	return pgtype.Int4{Int32: int32(*v), Valid: true}
}

func int8PtrParam(v *int64) pgtype.Int8 {
	if v == nil {
		return pgtype.Int8{}
	}
	return pgtype.Int8{Int64: *v, Valid: true}
}

func timeParam(v *time.Time) pgtype.Timestamptz {
	if v == nil {
		return pgtype.Timestamptz{}
	}
	return pgtype.Timestamptz{Time: *v, Valid: true}
}

func intPtrVal(v pgtype.Int4) *int {
	if !v.Valid {
		return nil
	}
	out := int(v.Int32)
	return &out
}

func int64PtrVal(v pgtype.Int8) *int64 {
	if !v.Valid {
		return nil
	}
	out := v.Int64
	return &out
}

func timePtrVal(v pgtype.Timestamptz) *time.Time {
	if !v.Valid {
		return nil
	}
	out := v.Time
	return &out
}

func textVal(v pgtype.Text) string {
	if !v.Valid {
		return ""
	}
	return v.String
}

func anyToInt64(v any) int64 {
	switch t := v.(type) {
	case int64:
		return t
	case int32:
		return int64(t)
	case float64:
		return int64(t)
	default:
		return 0
	}
}

func (s *Store) CreateAgentSession(ctx context.Context, sess AgentSession) error {
	return s.q.CreateAgentSession(ctx, sqlcgen.CreateAgentSessionParams{
		ID:        sess.ID,
		AgentID:   sess.AgentID,
		RoomID:    sess.RoomID,
		Column4:   sess.TableID,
		SeatID:    int4PtrParam(sess.SeatID),
		JoinMode:  sess.JoinMode,
		Status:    sess.Status,
		ExpiresAt: timeParam(&sess.ExpiresAt),
	})
}

func (s *Store) CreateMatchedTableAndSessions(ctx context.Context, tableID, roomID string, sb, bb int64, waiterSessionID string, second AgentSession, seat0, seat1 int) error {
	tx, err := s.Pool.BeginTx(ctx, pgx.TxOptions{})
	if err != nil {
		return err
	}
	defer tx.Rollback(ctx)

	qtx := s.q.WithTx(tx)
	if err := qtx.CreateTable(ctx, sqlcgen.CreateTableParams{
		ID:           tableID,
		RoomID:       textParam(roomID),
		Status:       "active",
		SmallBlindCc: sb,
		BigBlindCc:   bb,
	}); err != nil {
		return err
	}
	if err := qtx.CreateAgentSession(ctx, sqlcgen.CreateAgentSessionParams{
		ID:        second.ID,
		AgentID:   second.AgentID,
		RoomID:    second.RoomID,
		Column4:   second.TableID,
		SeatID:    int4Param(int32(seat1)),
		JoinMode:  second.JoinMode,
		Status:    second.Status,
		ExpiresAt: timestamptzParam(second.ExpiresAt),
	}); err != nil {
		return err
	}
	if rows, err := qtx.UpdateAgentSessionMatch(ctx, sqlcgen.UpdateAgentSessionMatchParams{
		ID:      waiterSessionID,
		TableID: textParam(tableID),
		SeatID:  int4Param(int32(seat0)),
	}); err != nil {
		return err
	} else if rows == 0 {
		return ErrNotFound
	}
	if rows, err := qtx.UpdateAgentSessionMatch(ctx, sqlcgen.UpdateAgentSessionMatchParams{
		ID:      second.ID,
		TableID: textParam(tableID),
		SeatID:  int4Param(int32(seat1)),
	}); err != nil {
		return err
	} else if rows == 0 {
		return ErrNotFound
	}
	return tx.Commit(ctx)
}

func (s *Store) GetAgentSession(ctx context.Context, sessionID string) (*AgentSession, error) {
	r, err := s.q.GetAgentSessionByID(ctx, sessionID)
	if err != nil {
		return nil, mapNotFound(err)
	}
	return &AgentSession{
		ID:        r.ID,
		AgentID:   r.AgentID,
		RoomID:    r.RoomID,
		TableID:   textVal(r.TableID),
		SeatID:    intPtrVal(r.SeatID),
		JoinMode:  r.JoinMode,
		Status:    r.Status,
		ExpiresAt: r.ExpiresAt.Time,
		CreatedAt: r.CreatedAt.Time,
		ClosedAt:  timePtrVal(r.ClosedAt),
	}, nil
}

func (s *Store) UpdateAgentSessionMatch(ctx context.Context, sessionID, tableID string, seatID int) error {
	rows, err := s.q.UpdateAgentSessionMatch(ctx, sqlcgen.UpdateAgentSessionMatchParams{
		ID:      sessionID,
		TableID: textParam(tableID),
		SeatID:  int4Param(int32(seatID)),
	})
	if err != nil {
		return err
	}
	if rows == 0 {
		return ErrNotFound
	}
	return nil
}

func (s *Store) CloseAgentSession(ctx context.Context, sessionID string) error {
	rows, err := s.q.CloseAgentSession(ctx, sessionID)
	if err != nil {
		return err
	}
	if rows == 0 {
		return ErrNotFound
	}
	return nil
}

func (s *Store) CloseAgentSessionsByTableID(ctx context.Context, tableID string) error {
	_, err := s.q.CloseAgentSessionsByTableID(ctx, tableID)
	return err
}

func (s *Store) MarkTableStatusByID(ctx context.Context, tableID, status string) error {
	rows, err := s.q.MarkTableStatusByID(ctx, sqlcgen.MarkTableStatusByIDParams{
		ID:     tableID,
		Status: status,
	})
	if err != nil {
		return err
	}
	if rows == 0 {
		return ErrNotFound
	}
	return nil
}

func (s *Store) InsertAgentActionRequest(ctx context.Context, req AgentActionRequest) (bool, error) {
	if req.ID == "" {
		req.ID = NewID()
	}
	rows, err := s.q.InsertAgentActionRequestIfAbsent(ctx, sqlcgen.InsertAgentActionRequestIfAbsentParams{
		ID:         req.ID,
		SessionID:  req.SessionID,
		RequestID:  req.RequestID,
		TurnID:     req.TurnID,
		ActionType: req.Action,
		AmountCc:   int8PtrParam(req.AmountCC),
		Column7:    req.ThoughtLog,
		Accepted:   req.Accepted,
		Column9:    req.Reason,
	})
	if err != nil {
		return false, err
	}
	return rows > 0, nil
}

func (s *Store) GetAgentActionRequest(ctx context.Context, sessionID, requestID string) (*AgentActionRequest, error) {
	r, err := s.q.GetAgentActionRequestBySessionAndRequest(ctx, sqlcgen.GetAgentActionRequestBySessionAndRequestParams{
		SessionID: sessionID,
		RequestID: requestID,
	})
	if err != nil {
		return nil, mapNotFound(err)
	}
	return &AgentActionRequest{
		ID:         r.ID,
		SessionID:  r.SessionID,
		RequestID:  r.RequestID,
		TurnID:     r.TurnID,
		Action:     r.ActionType,
		AmountCC:   int64PtrVal(r.AmountCc),
		ThoughtLog: textVal(r.ThoughtLog),
		Accepted:   r.Accepted,
		Reason:     textVal(r.Reason),
		CreatedAt:  r.CreatedAt.Time,
	}, nil
}

func (s *Store) CountAgentActionRequestsBySessionAndRequest(ctx context.Context, sessionID, requestID string) (int, error) {
	count, err := s.q.CountAgentActionRequestsBySessionAndRequest(ctx, sqlcgen.CountAgentActionRequestsBySessionAndRequestParams{
		SessionID: sessionID,
		RequestID: requestID,
	})
	return int(count), err
}

func (s *Store) UpsertAgentEventOffset(ctx context.Context, sessionID, lastEventID string) error {
	return s.q.UpsertAgentEventOffset(ctx, sqlcgen.UpsertAgentEventOffsetParams{
		SessionID:   sessionID,
		LastEventID: lastEventID,
	})
}

func (s *Store) GetAgentEventOffset(ctx context.Context, sessionID string) (*AgentEventOffset, error) {
	r, err := s.q.GetAgentEventOffsetBySessionID(ctx, sessionID)
	if err != nil {
		return nil, mapNotFound(err)
	}
	return &AgentEventOffset{
		SessionID:   r.SessionID,
		LastEventID: r.LastEventID,
		UpdatedAt:   r.UpdatedAt.Time,
	}, nil
}

func (s *Store) DebugSessionCount(ctx context.Context) (int, error) {
	count, err := s.q.CountAgentSessions(ctx)
	return int(count), err
}

func int32PtrParam(v *int32) pgtype.Int4 {
	if v == nil {
		return pgtype.Int4{}
	}
	return pgtype.Int4{Int32: *v, Valid: true}
}

func int32PtrVal(v pgtype.Int4) *int32 {
	if !v.Valid {
		return nil
	}
	out := v.Int32
	return &out
}

func (s *Store) InsertTableReplayEvent(
	ctx context.Context,
	tableID, handID string,
	globalSeq int64,
	handSeq *int32,
	eventType, actorAgentID string,
	payload json.RawMessage,
	schemaVersion int32,
) error {
	return s.q.InsertTableReplayEvent(ctx, sqlcgen.InsertTableReplayEventParams{
		ID:            NewID(),
		TableID:       tableID,
		Column3:       handID,
		GlobalSeq:     globalSeq,
		HandSeq:       int32PtrParam(handSeq),
		EventType:     eventType,
		Column7:       actorAgentID,
		Column8:       payload,
		SchemaVersion: schemaVersion,
	})
}

func (s *Store) ListTableReplayEventsFromSeq(ctx context.Context, tableID string, fromSeq int64, limit int) ([]TableReplayEvent, error) {
	if limit <= 0 {
		limit = 200
	}
	rows, err := s.q.ListTableReplayEventsFromSeq(ctx, sqlcgen.ListTableReplayEventsFromSeqParams{
		TableID:   tableID,
		GlobalSeq: fromSeq,
		Limit:     int32(limit),
	})
	if err != nil {
		return nil, err
	}
	out := make([]TableReplayEvent, 0, len(rows))
	for _, r := range rows {
		out = append(out, TableReplayEvent{
			ID:           r.ID,
			TableID:      r.TableID,
			HandID:       textVal(r.HandID),
			GlobalSeq:    r.GlobalSeq,
			HandSeq:      int32PtrVal(r.HandSeq),
			EventType:    r.EventType,
			ActorAgentID: textVal(r.ActorAgentID),
			Payload:      r.Payload,
			SchemaVer:    r.SchemaVersion,
			CreatedAt:    r.CreatedAt.Time,
		})
	}
	return out, nil
}

func (s *Store) GetTableReplayLastSeq(ctx context.Context, tableID string) (int64, error) {
	return s.q.GetTableReplayLastSeq(ctx, tableID)
}

func (s *Store) InsertTableReplaySnapshot(
	ctx context.Context,
	tableID string,
	atGlobalSeq int64,
	stateBlob json.RawMessage,
	schemaVersion int32,
) error {
	return s.q.InsertTableReplaySnapshot(ctx, sqlcgen.InsertTableReplaySnapshotParams{
		ID:            NewID(),
		TableID:       tableID,
		AtGlobalSeq:   atGlobalSeq,
		Column4:       stateBlob,
		SchemaVersion: schemaVersion,
	})
}

func (s *Store) GetLatestTableReplaySnapshotAtOrBefore(ctx context.Context, tableID string, atSeq int64) (*TableReplaySnapshot, error) {
	r, err := s.q.GetLatestTableReplaySnapshotAtOrBefore(ctx, sqlcgen.GetLatestTableReplaySnapshotAtOrBeforeParams{
		TableID:     tableID,
		AtGlobalSeq: atSeq,
	})
	if err != nil {
		return nil, mapNotFound(err)
	}
	return &TableReplaySnapshot{
		ID:          r.ID,
		TableID:     r.TableID,
		AtGlobalSeq: r.AtGlobalSeq,
		StateBlob:   r.StateBlob,
		SchemaVer:   r.SchemaVersion,
		CreatedAt:   r.CreatedAt.Time,
	}, nil
}

func (s *Store) ListHandsByTableID(ctx context.Context, tableID string) ([]Hand, error) {
	rows, err := s.q.ListHandsByTableID(ctx, tableID)
	if err != nil {
		return nil, err
	}
	out := make([]Hand, 0, len(rows))
	for _, r := range rows {
		out = append(out, Hand{
			ID:            r.ID,
			TableID:       r.TableID,
			WinnerAgentID: textVal(r.WinnerAgentID),
			PotCC:         int64PtrVal(r.PotCc),
			StreetEnd:     textVal(r.StreetEnd),
			StartedAt:     r.StartedAt.Time,
			EndedAt:       timePtrVal(r.EndedAt),
		})
	}
	return out, nil
}

func (s *Store) GetHandByID(ctx context.Context, handID string) (*Hand, error) {
	r, err := s.q.GetHandByID(ctx, handID)
	if err != nil {
		return nil, mapNotFound(err)
	}
	return &Hand{
		ID:            r.ID,
		TableID:       r.TableID,
		WinnerAgentID: textVal(r.WinnerAgentID),
		PotCC:         int64PtrVal(r.PotCc),
		StreetEnd:     textVal(r.StreetEnd),
		StartedAt:     r.StartedAt.Time,
		EndedAt:       timePtrVal(r.EndedAt),
	}, nil
}

func (s *Store) ListHandsByAgentID(ctx context.Context, agentID string, limit, offset int) ([]Hand, error) {
	if limit <= 0 {
		limit = 50
	}
	rows, err := s.q.ListHandsByAgentID(ctx, sqlcgen.ListHandsByAgentIDParams{
		AgentID: agentID,
		Limit:   int32(limit),
		Offset:  int32(offset),
	})
	if err != nil {
		return nil, err
	}
	out := make([]Hand, 0, len(rows))
	for _, r := range rows {
		out = append(out, Hand{
			ID:            r.ID,
			TableID:       r.TableID,
			WinnerAgentID: textVal(r.WinnerAgentID),
			PotCC:         int64PtrVal(r.PotCc),
			StreetEnd:     textVal(r.StreetEnd),
			StartedAt:     r.StartedAt.Time,
			EndedAt:       timePtrVal(r.EndedAt),
		})
	}
	return out, nil
}

func (s *Store) ListAgentTables(ctx context.Context, agentID string, limit, offset int) ([]AgentTableHistory, error) {
	if limit <= 0 {
		limit = 50
	}
	rows, err := s.q.ListAgentTables(ctx, sqlcgen.ListAgentTablesParams{
		AgentID: agentID,
		Limit:   int32(limit),
		Offset:  int32(offset),
	})
	if err != nil {
		return nil, err
	}
	out := make([]AgentTableHistory, 0, len(rows))
	for _, r := range rows {
		var endedAt *time.Time
		switch v := r.LastHandEndedAt.(type) {
		case time.Time:
			vt := v
			endedAt = &vt
		case pgtype.Timestamptz:
			endedAt = timePtrVal(v)
		}
		out = append(out, AgentTableHistory{
			TableID:       r.ID,
			RoomID:        textVal(r.RoomID),
			Status:        r.Status,
			SmallBlindCC:  r.SmallBlindCc,
			BigBlindCC:    r.BigBlindCc,
			CreatedAt:     r.CreatedAt.Time,
			LastHandEnded: endedAt,
		})
	}
	return out, nil
}

func (s *Store) ListTableHistory(ctx context.Context, roomID, agentID string, limit, offset int) ([]AgentTableHistory, error) {
	if limit <= 0 {
		limit = 50
	}
	rows, err := s.q.ListTableHistory(ctx, sqlcgen.ListTableHistoryParams{
		Column1: roomID,
		Column2: agentID,
		Limit:   int32(limit),
		Offset:  int32(offset),
	})
	if err != nil {
		return nil, err
	}
	out := make([]AgentTableHistory, 0, len(rows))
	for _, r := range rows {
		var endedAt *time.Time
		switch v := r.LastHandEndedAt.(type) {
		case time.Time:
			vt := v
			endedAt = &vt
		case pgtype.Timestamptz:
			endedAt = timePtrVal(v)
		}
		out = append(out, AgentTableHistory{
			TableID:       r.ID,
			RoomID:        textVal(r.RoomID),
			Status:        r.Status,
			SmallBlindCC:  r.SmallBlindCc,
			BigBlindCC:    r.BigBlindCc,
			CreatedAt:     r.CreatedAt.Time,
			LastHandEnded: endedAt,
		})
	}
	return out, nil
}
