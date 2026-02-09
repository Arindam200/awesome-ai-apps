package main

import (
	"net/http"
	"net/http/httptest"
	"testing"
)

type flusherRecorder struct {
	*httptest.ResponseRecorder
	flushed bool
}

func (f *flusherRecorder) Flush() {
	f.flushed = true
}

func TestBodyCaptureMiddlewarePreservesFlusher(t *testing.T) {
	handler := http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		flusher, ok := w.(http.Flusher)
		if !ok {
			http.Error(w, "no flusher", http.StatusInternalServerError)
			return
		}
		flusher.Flush()
		w.WriteHeader(http.StatusOK)
	})

	mw := bodyCaptureMiddleware()
	rec := &flusherRecorder{ResponseRecorder: httptest.NewRecorder()}
	req := httptest.NewRequest(http.MethodGet, "/api/agent/sessions/abc/events", nil)
	mw(handler).ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("expected status 200, got %d", rec.Code)
	}
	if !rec.flushed {
		t.Fatal("expected flusher to be called")
	}
}

func TestBodyCaptureMiddlewareSkipsSSE(t *testing.T) {
	handler := http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		if _, ok := w.(*captureWriter); ok {
			http.Error(w, "wrapped", http.StatusInternalServerError)
			return
		}
		w.WriteHeader(http.StatusOK)
	})

	mw := bodyCaptureMiddleware()
	rec := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodGet, "/api/agent/sessions/abc/events", nil)
	req.Header.Set("Accept", "text/event-stream")
	mw(handler).ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("expected status 200, got %d", rec.Code)
	}
}
