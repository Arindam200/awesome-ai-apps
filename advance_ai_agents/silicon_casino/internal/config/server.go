package config

import "github.com/caarlos0/env/v11"

type ServerConfig struct {
	PostgresDSN string `env:"POSTGRES_DSN,required,notEmpty"`
	HTTPAddr    string `env:"HTTP_ADDR" envDefault:":8080"`

	AdminAPIKey string `env:"ADMIN_API_KEY"`

	Agent1Name string `env:"AGENT1_NAME"`
	Agent1Key  string `env:"AGENT1_KEY"`
	Agent2Name string `env:"AGENT2_NAME"`
	Agent2Key  string `env:"AGENT2_KEY"`

	CCPerUSD         float64 `env:"CC_PER_USD" envDefault:"1000"`
	OpenAIPricePer1K float64 `env:"OPENAI_PRICE_PER_1K_USD" envDefault:"0.0001"`
	KimiPricePer1K   float64 `env:"KIMI_PRICE_PER_1K_USD" envDefault:"0.0001"`
	OpenAIWeight     float64 `env:"OPENAI_WEIGHT" envDefault:"1.0"`
	KimiWeight       float64 `env:"KIMI_WEIGHT" envDefault:"1.0"`
	MaxBudgetUSD     float64 `env:"MAX_BUDGET_USD" envDefault:"20"`
	BindCooldownMins int     `env:"BIND_KEY_COOLDOWN_MINUTES" envDefault:"60"`
	OpenAIBaseURL    string  `env:"OPENAI_BASE_URL" envDefault:"https://api.openai.com/v1"`
	KimiBaseURL      string  `env:"KIMI_BASE_URL" envDefault:"https://api.moonshot.ai/v1"`
	AllowAnyVendorKey bool   `env:"ALLOW_ANY_VENDOR_KEY" envDefault:"false"`
}

func LoadServer() (ServerConfig, error) {
	var cfg ServerConfig
	err := env.Parse(&cfg)
	return cfg, err
}
