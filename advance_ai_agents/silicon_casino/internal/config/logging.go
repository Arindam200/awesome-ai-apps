package config

import "github.com/caarlos0/env/v11"

type LogConfig struct {
	Level string `env:"LOG_LEVEL" envDefault:"info"`
	File  string `env:"LOG_FILE"`
	MaxMB int    `env:"LOG_MAX_MB" envDefault:"10"`
}

func LoadLog() (LogConfig, error) {
	var cfg LogConfig
	err := env.Parse(&cfg)
	return cfg, err
}
