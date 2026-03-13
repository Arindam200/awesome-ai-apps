package main

import (
	"net/http"
	"net/http/httptest"
	"testing"

	"silicon-casino/internal/config"
	httptransport "silicon-casino/internal/transport/http"
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

	mw := httptransport.BodyCaptureMiddleware(4096)
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
		w.WriteHeader(http.StatusOK)
	})

	mw := httptransport.BodyCaptureMiddleware(4096)
	rec := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodGet, "/api/agent/sessions/abc/events", nil)
	req.Header.Set("Accept", "text/event-stream")
	mw(handler).ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("expected status 200, got %d", rec.Code)
	}
}

func TestDefaultProviderRates(t *testing.T) {
	cfg := config.ServerConfig{CCPerUSD: 1000}

	rates := defaultProviderRates(cfg)
	if len(rates) != 2 {
		t.Fatalf("expected 2 provider rates, got %d", len(rates))
	}
	if rates[0].Provider != "openrouter" {
		t.Fatalf("expected first provider openrouter, got %s", rates[0].Provider)
	}
	if rates[1].Provider != "nebius" {
		t.Fatalf("expected second provider nebius, got %s", rates[1].Provider)
	}
	if rates[0].Weight != 1.0 || rates[1].Weight != 1.0 {
		t.Fatalf("expected provider weights fixed to 1.0, got %f and %f", rates[0].Weight, rates[1].Weight)
	}
	if rates[0].PricePer1KTokensUSD != defaultOpenRouterPricePer1KUSD {
		t.Fatalf("expected openrouter price %f, got %f", defaultOpenRouterPricePer1KUSD, rates[0].PricePer1KTokensUSD)
	}
	if rates[1].PricePer1KTokensUSD != defaultNebiusPricePer1KUSD {
		t.Fatalf("expected nebius price %f, got %f", defaultNebiusPricePer1KUSD, rates[1].PricePer1KTokensUSD)
	}
}
