package config

import "github.com/caarlos0/env/v11"

type ServerConfig struct {
	PostgresDSN string `env:"POSTGRES_DSN,required,notEmpty"`
	HTTPAddr    string `env:"HTTP_ADDR" envDefault:":8080"`

	AdminAPIKey string `env:"ADMIN_API_KEY"`

	CCPerUSD          float64 `env:"CC_PER_USD" envDefault:"1000"`
	MaxBudgetUSD      float64 `env:"MAX_BUDGET_USD" envDefault:"20"`
	BindCooldownMins  int     `env:"BIND_KEY_COOLDOWN_MINUTES" envDefault:"60"`
	AllowAnyVendorKey bool    `env:"ALLOW_ANY_VENDOR_KEY" envDefault:"false"`

	SpectatorPushEnabled    bool   `env:"SPECTATOR_PUSH_ENABLED" envDefault:"false"`
	SpectatorPushConfigPath string `env:"SPECTATOR_PUSH_CONFIG_PATH"`
}

func LoadServer() (ServerConfig, error) {
	var cfg ServerConfig
	err := env.Parse(&cfg)
	return cfg, err
}
