package httptransport

import (
	"encoding/json"
	"errors"
	"net/http"

	appagent "silicon-casino/internal/app/agent"

	"github.com/go-chi/chi/v5"
)

type AgentHandlers struct {
	svc *appagent.Service
}

func NewAgentHandlers(svc *appagent.Service) *AgentHandlers {
	return &AgentHandlers{svc: svc}
}

func (h *AgentHandlers) Register() http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		var body struct {
			Name        string `json:"name"`
			Description string `json:"description"`
		}
		if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
			WriteHTTPError(w, http.StatusBadRequest, "invalid_json")
			return
		}
		resp, err := h.svc.Register(r.Context(), appagent.RegisterInput{Name: body.Name, Description: body.Description})
		if err != nil {
			if errors.Is(err, appagent.ErrInvalidRequest) {
				WriteHTTPError(w, http.StatusBadRequest, "invalid_request")
				return
			}
			WriteHTTPError(w, http.StatusInternalServerError, "internal_error")
			return
		}
		_ = json.NewEncoder(w).Encode(resp)
	}
}

func (h *AgentHandlers) Me() http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		agent, ok := AgentFromContext(r.Context())
		if !ok {
			w.WriteHeader(http.StatusUnauthorized)
			return
		}
		resp, err := h.svc.Me(r.Context(), agent)
		if err != nil {
			WriteHTTPError(w, http.StatusInternalServerError, "internal_error")
			return
		}
		_ = json.NewEncoder(w).Encode(resp)
	}
}

func (h *AgentHandlers) Claim() http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		var body struct {
			AgentID   string `json:"agent_id"`
			ClaimCode string `json:"claim_code"`
		}
		if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
			WriteHTTPError(w, http.StatusBadRequest, "invalid_json")
			return
		}
		resp, err := h.svc.Claim(r.Context(), appagent.ClaimInput{AgentID: body.AgentID, ClaimCode: body.ClaimCode})
		if err != nil {
			switch {
			case errors.Is(err, appagent.ErrInvalidRequest):
				WriteHTTPError(w, http.StatusBadRequest, "invalid_request")
			case errors.Is(err, appagent.ErrInvalidClaim):
				WriteHTTPError(w, http.StatusUnauthorized, "invalid_claim")
			default:
				WriteHTTPError(w, http.StatusInternalServerError, "internal_error")
			}
			return
		}
		_ = json.NewEncoder(w).Encode(resp)
	}
}

func (h *AgentHandlers) ClaimByCode() http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		claimCode := chi.URLParam(r, "claim_code")
		resp, err := h.svc.ClaimByCode(r.Context(), claimCode)
		if err != nil {
			switch {
			case errors.Is(err, appagent.ErrInvalidRequest):
				WriteHTTPError(w, http.StatusBadRequest, "invalid_request")
			case errors.Is(err, appagent.ErrClaimNotFound):
				WriteHTTPError(w, http.StatusNotFound, "claim_not_found")
			default:
				WriteHTTPError(w, http.StatusInternalServerError, "internal_error")
			}
			return
		}
		_ = json.NewEncoder(w).Encode(resp)
	}
}

func (h *AgentHandlers) BindKey() http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		var body struct {
			Provider  string  `json:"provider"`
			APIKey    string  `json:"api_key"`
			BudgetUSD float64 `json:"budget_usd"`
		}
		if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
			WriteHTTPError(w, http.StatusBadRequest, "invalid_json")
			return
		}
		agent, ok := AgentFromContext(r.Context())
		if !ok || agent == nil {
			w.WriteHeader(http.StatusUnauthorized)
			return
		}
		resp, err := h.svc.BindKey(r.Context(), agent, appagent.BindKeyInput{
			Provider:  body.Provider,
			APIKey:    body.APIKey,
			BudgetUSD: body.BudgetUSD,
		})
		if err != nil {
			switch {
			case errors.Is(err, appagent.ErrInvalidRequest):
				WriteHTTPError(w, http.StatusBadRequest, "invalid_request")
			case errors.Is(err, appagent.ErrBudgetExceedsLimit):
				WriteHTTPError(w, http.StatusBadRequest, "budget_exceeds_limit")
			case errors.Is(err, appagent.ErrInvalidProvider):
				WriteHTTPError(w, http.StatusBadRequest, "invalid_provider")
			case errors.Is(err, appagent.ErrCooldownActive):
				WriteHTTPError(w, http.StatusTooManyRequests, "cooldown_active")
			case errors.Is(err, appagent.ErrAPIKeyAlreadyBound):
				WriteHTTPError(w, http.StatusConflict, "api_key_already_bound")
			case errors.Is(err, appagent.ErrInvalidVendorKey):
				WriteHTTPError(w, http.StatusUnauthorized, "invalid_vendor_key")
			case errors.Is(err, appagent.ErrInsufficientVendorBalance):
				WriteHTTPError(w, http.StatusBadRequest, "insufficient_vendor_balance")
			case errors.Is(err, appagent.ErrAgentBlacklisted):
				w.WriteHeader(http.StatusForbidden)
				payload := map[string]any{"error": "agent_blacklisted"}
				var be *appagent.BlacklistError
				if errors.As(err, &be) && be.Reason != "" {
					payload["reason"] = be.Reason
				}
				_ = json.NewEncoder(w).Encode(payload)
			default:
				WriteHTTPError(w, http.StatusInternalServerError, "internal_error")
			}
			return
		}
		_ = json.NewEncoder(w).Encode(resp)
	}
}
