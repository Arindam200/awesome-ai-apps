package session

import "errors"

var (
	ErrInvalidRequest = errors.New("invalid_request")
	ErrTableNotFound  = errors.New("table_not_found")
)
