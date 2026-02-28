package logging

import (
	"io"
	"os"
	"path/filepath"

	"silicon-casino/internal/config"

	"github.com/rs/zerolog"
	"github.com/rs/zerolog/log"
)

var sharedOutput io.Writer = os.Stdout

func Init(cfg config.LogConfig) {
	level := zerolog.InfoLevel
	if parsed, err := zerolog.ParseLevel(cfg.Level); err == nil {
		level = parsed
	}

	if cfg.File == "" {
		if cwd, err := os.Getwd(); err == nil {
			cfg.File = filepath.Join(cwd, "game-server.log")
		}
	}

	output := sharedOutput
	if cfg.File != "" {
		fileWriter, err := newSizeLimitedWriter(cfg.File, cfg.MaxMB)
		if err == nil {
			output = fileWriter
		}
	}

	zerolog.SetGlobalLevel(level)
	logger := zerolog.New(output).With().Timestamp().Logger()
	log.Logger = logger
	sharedOutput = output
}

func Writer() io.Writer {
	return sharedOutput
}
