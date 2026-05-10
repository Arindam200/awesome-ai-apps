package spectatorpush

import (
	"os"
	"path/filepath"
	"testing"

	"silicon-casino/internal/config"
)

func TestConfigFromServerFiltersTargets(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "targets.json")
	raw := `[
	  {"platform":"discord","endpoint":"https://a","scope_type":"room","scope_value":"mid","enabled":true},
	  {"platform":"feishu","endpoint":"","scope_type":"room","scope_value":"mid","enabled":true},
	  {"platform":"discord","endpoint":"https://b","scope_type":"invalid","scope_value":"mid","enabled":true}
	]`
	if err := os.WriteFile(path, []byte(raw), 0o600); err != nil {
		t.Fatalf("write config file: %v", err)
	}

	scfg := config.ServerConfig{
		SpectatorPushEnabled:    true,
		SpectatorPushConfigPath: path,
	}
	cfg, err := ConfigFromServer(scfg)
	if err != nil {
		t.Fatalf("config parse failed: %v", err)
	}
	if len(cfg.Targets) != 1 {
		t.Fatalf("expected 1 filtered target, got %d", len(cfg.Targets))
	}
	if cfg.Targets[0].Platform != "discord" {
		t.Fatalf("unexpected platform: %s", cfg.Targets[0].Platform)
	}
}

func TestConfigFromServerUsesConfigPath(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "targets.json")
	fileJSON := `[{"platform":"discord","endpoint":"https://from-file","scope_type":"room","scope_value":"mid","enabled":true}]`
	if err := os.WriteFile(path, []byte(fileJSON), 0o600); err != nil {
		t.Fatalf("write config file: %v", err)
	}

	scfg := config.ServerConfig{
		SpectatorPushEnabled:    true,
		SpectatorPushConfigPath: path,
	}
	cfg, err := ConfigFromServer(scfg)
	if err != nil {
		t.Fatalf("config parse failed: %v", err)
	}
	if len(cfg.Targets) != 1 {
		t.Fatalf("expected 1 target, got %d", len(cfg.Targets))
	}
	if cfg.Targets[0].Endpoint != "https://from-file" {
		t.Fatalf("expected endpoint from file, got %s", cfg.Targets[0].Endpoint)
	}
}

func TestConfigFromServerConfigPathReadError(t *testing.T) {
	scfg := config.ServerConfig{
		SpectatorPushEnabled:    true,
		SpectatorPushConfigPath: "/tmp/not-exist-spectator-push.json",
	}
	if _, err := ConfigFromServer(scfg); err == nil {
		t.Fatal("expected read error for missing config path")
	}
}
