package config

import (
	"github.com/BurntSushi/toml"
)
const ConfigPath = "../../../config.toml"
// 配置文件-嵌套形式
type Config struct {
	GRPC GRPCConfig `toml:"grpc"`
}

type GRPCConfig struct {
	Client GRPCClientConfig `toml:"client"`
}

type GRPCClientConfig struct {
	Host string `toml:"host"`
	Port int    `toml:"port"`
}

func LoadConfig(path string) (*Config, error) {
	var cfg Config
	if _, err := toml.DecodeFile(path, &cfg); err != nil { // 传入路径和目标结构体指针
		return nil, err
	}
	return &cfg, nil
}


