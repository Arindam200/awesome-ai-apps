package config

import "testing"

func TestLoadLogDefaults(t *testing.T) {
	cfg, err := LoadLog()
	if err != nil {
		t.Fatalf("LoadLog() error = %v", err)
	}
	if cfg.Level != "info" {
		t.Fatalf("Level = %q, want info", cfg.Level)
	}
}

func TestLoadLogParse(t *testing.T) {
	t.Setenv("LOG_LEVEL", "debug")

	cfg, err := LoadLog()
	if err != nil {
		t.Fatalf("LoadLog() error = %v", err)
	}
	if cfg.Level != "debug" {
		t.Fatalf("unexpected log config: %+v", cfg)
	}
}
