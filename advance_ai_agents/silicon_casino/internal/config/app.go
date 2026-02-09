package config

type AppConfig struct {
	Server ServerConfig
	Log    LogConfig
}

func LoadApp() (AppConfig, error) {
	logCfg, err := LoadLog()
	if err != nil {
		return AppConfig{}, err
	}
	serverCfg, err := LoadServer()
	if err != nil {
		return AppConfig{}, err
	}
	return AppConfig{
		Server: serverCfg,
		Log:    logCfg,
	}, nil
}
