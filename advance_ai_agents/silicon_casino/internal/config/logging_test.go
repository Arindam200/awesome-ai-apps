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
	if cfg.Pretty {
		t.Fatal("Pretty = true, want false")
	}
	if cfg.SampleEvery != 0 {
		t.Fatalf("SampleEvery = %d, want 0", cfg.SampleEvery)
	}
}

func TestLoadLogParse(t *testing.T) {
	t.Setenv("LOG_LEVEL", "debug")
	t.Setenv("LOG_PRETTY", "1")
	t.Setenv("LOG_SAMPLE_EVERY", "12")

	cfg, err := LoadLog()
	if err != nil {
		t.Fatalf("LoadLog() error = %v", err)
	}
	if cfg.Level != "debug" || !cfg.Pretty || cfg.SampleEvery != 12 {
		t.Fatalf("unexpected log config: %+v", cfg)
	}
}
