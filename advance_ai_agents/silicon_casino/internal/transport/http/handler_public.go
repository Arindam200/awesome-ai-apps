package httptransport

import (
	"encoding/json"
	"errors"
	"net/http"
	"strconv"
	"time"

	apppublic "silicon-casino/internal/app/public"
	appsession "silicon-casino/internal/app/session"

	"github.com/go-chi/chi/v5"
)

type PublicHandlers struct {
	publicSvc  *apppublic.Service
	sessionSvc *appsession.Service
}

func NewPublicHandlers(publicSvc *apppublic.Service, sessionSvc *appsession.Service) *PublicHandlers {
	return &PublicHandlers{publicSvc: publicSvc, sessionSvc: sessionSvc}
}

func (h *PublicHandlers) Rooms() http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		resp, err := h.publicSvc.Rooms(r.Context())
		if err != nil {
			WriteHTTPError(w, http.StatusInternalServerError, "internal_error")
			return
		}
		_ = json.NewEncoder(w).Encode(resp)
	}
}

func (h *PublicHandlers) Tables() http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		roomID := r.URL.Query().Get("room_id")
		limit, offset := ParsePagination(r)
		resp, err := h.publicSvc.Tables(r.Context(), roomID, limit, offset)
		if err != nil {
			WriteHTTPError(w, http.StatusInternalServerError, "internal_error")
			return
		}
		_ = json.NewEncoder(w).Encode(resp)
	}
}

func (h *PublicHandlers) TableHistory() http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		limit, offset := ParsePagination(r)
		resp, err := h.publicSvc.TableHistory(r.Context(), r.URL.Query().Get("room_id"), r.URL.Query().Get("agent_id"), limit, offset)
		if err != nil {
			WriteHTTPError(w, http.StatusInternalServerError, "internal_error")
			return
		}
		_ = json.NewEncoder(w).Encode(resp)
	}
}

func (h *PublicHandlers) AgentTable() http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		agentID := r.URL.Query().Get("agent_id")
		resp, err := h.sessionSvc.FindTableByAgent(agentID)
		if err != nil {
			switch {
			case errors.Is(err, appsession.ErrInvalidRequest):
				WriteHTTPError(w, http.StatusBadRequest, "invalid_request")
			case errors.Is(err, appsession.ErrTableNotFound):
				WriteHTTPError(w, http.StatusNotFound, "table_not_found")
			default:
				WriteHTTPError(w, http.StatusInternalServerError, "internal_error")
			}
			return
		}
		_ = json.NewEncoder(w).Encode(resp)
	}
}

func (h *PublicHandlers) AgentTables() http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		agentID := chi.URLParam(r, "agent_id")
		limit, offset := ParsePagination(r)
		resp, err := h.publicSvc.AgentTables(r.Context(), agentID, limit, offset)
		if err != nil {
			if errors.Is(err, apppublic.ErrInvalidRequest) {
				WriteHTTPError(w, http.StatusBadRequest, "invalid_request")
				return
			}
			WriteHTTPError(w, http.StatusInternalServerError, "internal_error")
			return
		}
		_ = json.NewEncoder(w).Encode(resp)
	}
}

func (h *PublicHandlers) AgentProfile() http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		agentID := chi.URLParam(r, "agent_id")
		limit, offset := ParsePagination(r)
		if r.URL.Query().Get("limit") == "" {
			limit = 20
		}
		resp, err := h.publicSvc.AgentProfile(r.Context(), agentID, limit, offset)
		if err != nil {
			switch {
			case errors.Is(err, apppublic.ErrInvalidRequest):
				WriteHTTPError(w, http.StatusBadRequest, "invalid_request")
			case errors.Is(err, apppublic.ErrNotFound):
				WriteHTTPError(w, http.StatusNotFound, "not_found")
			default:
				WriteHTTPError(w, http.StatusInternalServerError, "internal_error")
			}
			return
		}
		_ = json.NewEncoder(w).Encode(resp)
	}
}

func (h *PublicHandlers) TableReplay() http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		start := time.Now()
		defer func() {
			replayQueryP95MS.Set(time.Since(start).Milliseconds())
		}()
		replayQueryTotal.Add(1)

		tableID := chi.URLParam(r, "table_id")
		fromSeq := int64(1)
		if v := r.URL.Query().Get("from_seq"); v != "" {
			n, err := strconv.ParseInt(v, 10, 64)
			if err != nil || n < 1 {
				replayQueryErrorsTotal.Add(1)
				WriteHTTPError(w, http.StatusBadRequest, "invalid_request")
				return
			}
			fromSeq = n
		}
		limit := 200
		if v := r.URL.Query().Get("limit"); v != "" {
			n, err := strconv.Atoi(v)
			if err != nil || n < 1 {
				replayQueryErrorsTotal.Add(1)
				WriteHTTPError(w, http.StatusBadRequest, "invalid_request")
				return
			}
			limit = n
		}
		if limit > 500 {
			limit = 500
		}
		resp, err := h.publicSvc.TableReplay(r.Context(), tableID, fromSeq, limit)
		if err != nil {
			replayQueryErrorsTotal.Add(1)
			switch {
			case errors.Is(err, apppublic.ErrInvalidRequest):
				WriteHTTPError(w, http.StatusBadRequest, "invalid_request")
			case errors.Is(err, apppublic.ErrTableNotFound):
				WriteHTTPError(w, http.StatusNotFound, "table_not_found")
			default:
				WriteHTTPError(w, http.StatusInternalServerError, "internal_error")
			}
			return
		}
		_ = json.NewEncoder(w).Encode(resp)
	}
}

func (h *PublicHandlers) TableTimeline() http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		start := time.Now()
		defer func() {
			replayQueryP95MS.Set(time.Since(start).Milliseconds())
		}()
		replayQueryTotal.Add(1)

		tableID := chi.URLParam(r, "table_id")
		resp, err := h.publicSvc.TableTimeline(r.Context(), tableID)
		if err != nil {
			replayQueryErrorsTotal.Add(1)
			switch {
			case errors.Is(err, apppublic.ErrInvalidRequest):
				WriteHTTPError(w, http.StatusBadRequest, "invalid_request")
			case errors.Is(err, apppublic.ErrTableNotFound):
				WriteHTTPError(w, http.StatusNotFound, "table_not_found")
			default:
				WriteHTTPError(w, http.StatusInternalServerError, "internal_error")
			}
			return
		}
		_ = json.NewEncoder(w).Encode(resp)
	}
}

func (h *PublicHandlers) TableSnapshot() http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		replayQueryTotal.Add(1)
		start := time.Now()
		defer func() {
			replayQueryP95MS.Set(time.Since(start).Milliseconds())
		}()

		tableID := chi.URLParam(r, "table_id")
		atSeqRaw := r.URL.Query().Get("at_seq")
		if atSeqRaw == "" {
			replayQueryErrorsTotal.Add(1)
			WriteHTTPError(w, http.StatusBadRequest, "invalid_request")
			return
		}
		atSeq, err := strconv.ParseInt(atSeqRaw, 10, 64)
		if err != nil || atSeq < 1 {
			replayQueryErrorsTotal.Add(1)
			WriteHTTPError(w, http.StatusBadRequest, "invalid_request")
			return
		}

		resp, err := h.publicSvc.TableSnapshot(r.Context(), tableID, atSeq)
		if err != nil {
			replayQueryErrorsTotal.Add(1)
			switch {
			case errors.Is(err, apppublic.ErrInvalidRequest):
				WriteHTTPError(w, http.StatusBadRequest, "invalid_request")
			case errors.Is(err, apppublic.ErrTableNotFound):
				WriteHTTPError(w, http.StatusNotFound, "table_not_found")
			default:
				WriteHTTPError(w, http.StatusInternalServerError, "internal_error")
			}
			return
		}

		if resp.Hit {
			replaySnapshotHitTotal.Add(1)
		} else {
			replaySnapshotMissTotal.Add(1)
		}
		hits := replaySnapshotHitTotal.Value()
		total := hits + replaySnapshotMissTotal.Value()
		if total > 0 {
			replaySnapshotHitRatio.Set(float64(hits) / float64(total))
		}
		replaySnapshotRebuildMS.Set(time.Since(start).Milliseconds())
		_ = json.NewEncoder(w).Encode(resp)
	}
}

func (h *PublicHandlers) Leaderboard() http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		limit, offset := ParsePagination(r)
		if limit > 100 {
			limit = 100
		}
		window := r.URL.Query().Get("window")
		if window == "" {
			window = "30d"
		}
		if !isAllowedLeaderboardWindow(window) {
			WriteHTTPError(w, http.StatusBadRequest, "invalid_request")
			return
		}
		roomID := r.URL.Query().Get("room_id")
		if roomID == "" {
			roomID = "all"
		}
		if !isAllowedLeaderboardRoom(roomID) {
			WriteHTTPError(w, http.StatusBadRequest, "invalid_request")
			return
		}
		sortBy := r.URL.Query().Get("sort")
		if sortBy == "" {
			sortBy = "score"
		}
		if !isAllowedLeaderboardSort(sortBy) {
			WriteHTTPError(w, http.StatusBadRequest, "invalid_request")
			return
		}
		resp, err := h.publicSvc.Leaderboard(r.Context(), apppublic.LeaderboardQuery{
			Window: window,
			RoomID: roomID,
			SortBy: sortBy,
		}, limit, offset)
		if err != nil {
			WriteHTTPError(w, http.StatusInternalServerError, "internal_error")
			return
		}
		_ = json.NewEncoder(w).Encode(resp)
	}
}

func isAllowedLeaderboardWindow(v string) bool {
	return v == "7d" || v == "30d" || v == "all"
}

func isAllowedLeaderboardRoom(v string) bool {
	return v == "all" || v == "low" || v == "mid" || v == "high"
}

func isAllowedLeaderboardSort(v string) bool {
	return v == "score" || v == "net_cc_from_play" || v == "hands_played" || v == "win_rate"
}
