package config

import "github.com/caarlos0/env/v11"

type TestConfig struct {
	TestPostgresDSN string `env:"TEST_POSTGRES_DSN,required,notEmpty"`
}

func LoadTest() (TestConfig, error) {
	var cfg TestConfig
	err := env.Parse(&cfg)
	return cfg, err
}
