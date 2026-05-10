package runtime

import (
	"errors"
	"net/http"
)

func MapSessionCreateError(err error) (int, string) {
	switch err.Error() {
	case "invalid_api_key":
		return http.StatusUnauthorized, "invalid_api_key"
	case "room_not_found":
		return http.StatusNotFound, "room_not_found"
	case "insufficient_buyin":
		return http.StatusBadRequest, "insufficient_buyin"
	case "no_available_room":
		return http.StatusBadRequest, "no_available_room"
	case "agent_already_in_session":
		return http.StatusConflict, "agent_already_in_session"
	case "invalid_action":
		return http.StatusBadRequest, "invalid_action"
	default:
		return http.StatusInternalServerError, "internal_error"
	}
}

func MapActionSubmitError(err error) (int, string) {
	switch {
	case errors.Is(err, errSessionNotFound):
		return http.StatusNotFound, "session_not_found"
	case errors.Is(err, errInvalidRequestID):
		return http.StatusBadRequest, "invalid_request_id"
	case errors.Is(err, errInvalidTurnID):
		return http.StatusBadRequest, "invalid_turn_id"
	case errors.Is(err, errNotYourTurn):
		return http.StatusBadRequest, "not_your_turn"
	case errors.Is(err, errInvalidAction):
		return http.StatusBadRequest, "invalid_action"
	case errors.Is(err, errInvalidRaise):
		return http.StatusBadRequest, "invalid_raise"
	case errors.Is(err, errTableClosing):
		return http.StatusConflict, "table_closing"
	case errors.Is(err, errTableClosed):
		return http.StatusGone, "table_closed"
	case errors.Is(err, errOpponentDown):
		return http.StatusConflict, "opponent_disconnected"
	default:
		return http.StatusInternalServerError, "internal_error"
	}
}
