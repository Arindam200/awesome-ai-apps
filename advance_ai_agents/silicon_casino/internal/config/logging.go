package config

import "github.com/caarlos0/env/v11"

type LogConfig struct {
	Level       string `env:"LOG_LEVEL" envDefault:"info"`
	Pretty      bool   `env:"LOG_PRETTY" envDefault:"false"`
	SampleEvery int    `env:"LOG_SAMPLE_EVERY" envDefault:"0"`
	File        string `env:"LOG_FILE"`
	MaxMB       int    `env:"LOG_MAX_MB" envDefault:"10"`
}

func LoadLog() (LogConfig, error) {
	var cfg LogConfig
	err := env.Parse(&cfg)
	return cfg, err
}
