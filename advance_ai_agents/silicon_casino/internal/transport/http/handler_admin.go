package httptransport

import (
	"encoding/json"
	"net/http"
	"strconv"
	"strings"
	"time"

	"silicon-casino/internal/store"
)

type AdminHandlers struct {
	store *store.Store
}

func NewAdminHandlers(st *store.Store) *AdminHandlers {
	return &AdminHandlers{store: st}
}

func (h *AdminHandlers) Health() http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		if err := h.store.Ping(r.Context()); err != nil {
			w.WriteHeader(http.StatusServiceUnavailable)
			_ = json.NewEncoder(w).Encode(map[string]any{"ok": false, "db": "down"})
			return
		}
		_ = json.NewEncoder(w).Encode(map[string]any{"ok": true, "db": "up"})
	}
}

func (h *AdminHandlers) Agents() http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		limit, offset := ParsePagination(r)
		items, err := h.store.ListAgents(r.Context(), limit, offset)
		if err != nil {
			WriteHTTPError(w, http.StatusInternalServerError, "internal_error")
			return
		}
		_ = json.NewEncoder(w).Encode(map[string]any{"items": items, "limit": limit, "offset": offset})
	}
}

func (h *AdminHandlers) Ledger() http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		limit, offset := ParsePagination(r)
		f := store.LedgerFilter{AgentID: r.URL.Query().Get("agent_id"), HandID: r.URL.Query().Get("hand_id")}
		if v := r.URL.Query().Get("from"); v != "" {
			if t, err := time.Parse(time.RFC3339, v); err == nil {
				f.From = &t
			}
		}
		if v := r.URL.Query().Get("to"); v != "" {
			if t, err := time.Parse(time.RFC3339, v); err == nil {
				f.To = &t
			}
		}
		items, err := h.store.ListLedgerEntries(r.Context(), f, limit, offset)
		if err != nil {
			WriteHTTPError(w, http.StatusInternalServerError, "internal_error")
			return
		}
		_ = json.NewEncoder(w).Encode(map[string]any{"items": items, "limit": limit, "offset": offset})
	}
}

func (h *AdminHandlers) Topup() http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		var body struct {
			AgentID  string `json:"agent_id"`
			AmountCC int64  `json:"amount_cc"`
		}
		if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
			WriteHTTPError(w, http.StatusBadRequest, "invalid_json")
			return
		}
		if body.AgentID == "" || body.AmountCC <= 0 {
			WriteHTTPError(w, http.StatusBadRequest, "invalid_request")
			return
		}
		refID := strconv.FormatInt(time.Now().UnixNano(), 10)
		bal, err := h.store.Credit(r.Context(), body.AgentID, body.AmountCC, "topup_credit", "topup", refID)
		if err != nil {
			WriteHTTPError(w, http.StatusInternalServerError, "internal_error")
			return
		}
		_ = json.NewEncoder(w).Encode(map[string]any{"ok": true, "balance_cc": bal})
	}
}

func (h *AdminHandlers) Rooms() http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		switch r.Method {
		case http.MethodGet:
			items, err := h.store.ListRooms(r.Context())
			if err != nil {
				WriteHTTPError(w, http.StatusInternalServerError, "internal_error")
				return
			}
			_ = json.NewEncoder(w).Encode(map[string]any{"items": items})
		case http.MethodPost:
			var body struct {
				Name       string `json:"name"`
				MinBuyinCC int64  `json:"min_buyin_cc"`
				SmallBlind int64  `json:"small_blind_cc"`
				BigBlind   int64  `json:"big_blind_cc"`
			}
			if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
				WriteHTTPError(w, http.StatusBadRequest, "invalid_json")
				return
			}
			if body.Name == "" || body.MinBuyinCC <= 0 || body.SmallBlind <= 0 || body.BigBlind <= 0 {
				WriteHTTPError(w, http.StatusBadRequest, "invalid_request")
				return
			}
			id, err := h.store.CreateRoom(r.Context(), body.Name, body.MinBuyinCC, body.SmallBlind, body.BigBlind)
			if err != nil {
				WriteHTTPError(w, http.StatusInternalServerError, "internal_error")
				return
			}
			_ = json.NewEncoder(w).Encode(map[string]any{"ok": true, "room_id": id})
		default:
			WriteHTTPError(w, http.StatusMethodNotAllowed, "method_not_allowed")
		}
	}
}

func (h *AdminHandlers) ProviderRates() http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		switch r.Method {
		case http.MethodGet:
			items, err := h.store.ListProviderRates(r.Context())
			if err != nil {
				WriteHTTPError(w, http.StatusInternalServerError, "internal_error")
				return
			}
			_ = json.NewEncoder(w).Encode(map[string]any{"items": items})
		case http.MethodPost:
			var body struct {
				Provider            string  `json:"provider"`
				PricePer1KTokensUSD float64 `json:"price_per_1k_tokens_usd"`
				CCPerUSD            float64 `json:"cc_per_usd"`
				Weight              float64 `json:"weight"`
			}
			if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
				WriteHTTPError(w, http.StatusBadRequest, "invalid_json")
				return
			}
			body.Provider = strings.ToLower(strings.TrimSpace(body.Provider))
			if body.Provider == "" || body.PricePer1KTokensUSD <= 0 || body.CCPerUSD <= 0 || body.Weight <= 0 {
				WriteHTTPError(w, http.StatusBadRequest, "invalid_request")
				return
			}
			if err := h.store.UpsertProviderRate(r.Context(), body.Provider, body.PricePer1KTokensUSD, body.CCPerUSD, body.Weight); err != nil {
				WriteHTTPError(w, http.StatusInternalServerError, "internal_error")
				return
			}
			_ = json.NewEncoder(w).Encode(map[string]any{"ok": true})
		default:
			WriteHTTPError(w, http.StatusMethodNotAllowed, "method_not_allowed")
		}
	}
}
