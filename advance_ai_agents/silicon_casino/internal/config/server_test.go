package config

import "testing"

func TestLoadServerDefaults(t *testing.T) {
	t.Setenv("POSTGRES_DSN", "postgres://localhost:5432/apa?sslmode=disable")

	cfg, err := LoadServer()
	if err != nil {
		t.Fatalf("LoadServer() error = %v", err)
	}
	if cfg.HTTPAddr != ":8080" {
		t.Fatalf("HTTPAddr = %q, want :8080", cfg.HTTPAddr)
	}
	if cfg.MaxBudgetUSD != 20 {
		t.Fatalf("MaxBudgetUSD = %v, want 20", cfg.MaxBudgetUSD)
	}
	if cfg.BindCooldownMins != 60 {
		t.Fatalf("BindCooldownMins = %d, want 60", cfg.BindCooldownMins)
	}
	if cfg.AllowAnyVendorKey {
		t.Fatal("AllowAnyVendorKey = true, want false")
	}
}

func TestLoadServerRequiresPostgresDSN(t *testing.T) {
	t.Setenv("POSTGRES_DSN", "")

	_, err := LoadServer()
	if err == nil {
		t.Fatal("LoadServer() expected error, got nil")
	}
}

func TestLoadServerParseTypes(t *testing.T) {
	t.Setenv("POSTGRES_DSN", "postgres://localhost:5432/apa?sslmode=disable")
	t.Setenv("CC_PER_USD", "2500")
	t.Setenv("BIND_KEY_COOLDOWN_MINUTES", "30")
	t.Setenv("ALLOW_ANY_VENDOR_KEY", "true")

	cfg, err := LoadServer()
	if err != nil {
		t.Fatalf("LoadServer() error = %v", err)
	}
	if cfg.CCPerUSD != 2500 {
		t.Fatalf("CCPerUSD = %v, want 2500", cfg.CCPerUSD)
	}
	if cfg.BindCooldownMins != 30 {
		t.Fatalf("BindCooldownMins = %d, want 30", cfg.BindCooldownMins)
	}
	if !cfg.AllowAnyVendorKey {
		t.Fatal("AllowAnyVendorKey = false, want true")
	}
}
