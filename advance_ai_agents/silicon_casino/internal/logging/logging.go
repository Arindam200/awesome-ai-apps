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
			if cfg.Pretty {
				output = io.MultiWriter(fileWriter, zerolog.ConsoleWriter{Out: os.Stdout})
			} else {
				output = fileWriter
			}
		} else if cfg.Pretty {
			output = zerolog.ConsoleWriter{Out: os.Stdout}
		}
	} else if cfg.Pretty {
		output = zerolog.ConsoleWriter{Out: os.Stdout}
	}

	zerolog.SetGlobalLevel(level)
	logger := zerolog.New(output).With().Timestamp().Logger()
	if n := cfg.SampleEvery; n > 1 {
		logger = logger.Sample(&zerolog.BasicSampler{N: uint32(n)})
	}
	log.Logger = logger
	sharedOutput = output
}

func Writer() io.Writer {
	return sharedOutput
}
