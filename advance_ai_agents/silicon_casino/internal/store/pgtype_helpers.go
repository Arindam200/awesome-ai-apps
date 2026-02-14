package store

import (
	"errors"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgtype"
)

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
