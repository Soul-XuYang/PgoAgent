package config

import (
	"path/filepath"
	"runtime"
	"time"
	"github.com/BurntSushi/toml"
	"github.com/joho/godotenv"
	"os"
)

const (
	AppName = "PgoAgent"
	Author  = "soul_xuyang"
)

func getConfigPath() string {
	_, filename, _, _ := runtime.Caller(0)
	dir := filepath.Dir(filename)
	return filepath.Join(dir, "..", "..", "..", "config.toml")
}

var StartRunTime = time.Now().Format("2006-01-02 15:04") // 程序启动的事件
// 配置文件-嵌套形式
type Config struct {
	GRPC      GRPCConfig `toml:"grpc"`
	VERSION   string     `toml:"version"`
	WEBSERVER WebServer  `toml:"web"`
}

type GRPCConfig struct {
	Server GRPCServerConfig `toml:"server"`
}

type GRPCServerConfig struct {
	Host        string `toml:"host"`
	Port        int    `toml:"port"`
	SendSize    int    `toml:"send_size"`    // 添加：服务端接收上限（MB）
	ReceiveSize int    `toml:"receive_size"` // 添加：服务端发送上限（MB）
}

type WebServer struct {
	Config WebServerConfig `toml:"server"`
}
type WebServerConfig struct {
	Host    string `toml:"host"`
	Port    int    `toml:"port"`
	Timeout int    `toml:"timeout"`
	UseTLS bool    `toml:"use_tls"`
}

type EnvConfig struct {
    DSN string `toml:"DATABASE_URL"`
	JWTToken string `toml:"JWT_TOKEN"`
}
// 这里用path传入是因为公共的数据节省内存
func LoadEnv()(*EnvConfig,error) {
	_, filename, _, _ := runtime.Caller(0)
	dir := filepath.Dir(filename)
	EnvPath:= filepath.Join(dir, "..", "..", "..", ".env")
	if  err := godotenv.Load(EnvPath); err != nil {
		return nil,err
	}
    JWTToken := os.Getenv("JWT_TOKEN")
	if JWTToken == "" {
		JWTToken = "MY_SECRET_KEY"
	}
	return &EnvConfig{
		DSN: os.Getenv("DATABASE_URL"),
		JWTToken: JWTToken,
	},nil
}
func LoadConfig() (*Config, error) {
	_, filename, _, _ := runtime.Caller(0)
	dir := filepath.Dir(filename)
	path:= filepath.Join(dir, "..", "..", "..", "config.toml")
	var cfg Config
	if _, err := toml.DecodeFile(path, &cfg); err != nil { // 传入路径和目标结构体指针
		return nil, err
	}
	return &cfg, nil
}


var ConfigHandler, LoadErr = LoadConfig()
var EnvConfigHandler, LoadEnvErr = LoadEnv()
// 安全地获取 VERSION，如果 ConfigHandler 为 nil 则使用默认值
var VERSION = func() string {
	if ConfigHandler != nil {
		return ConfigHandler.VERSION
	}
	return "unknown" // 默认值，避免 nil pointer dereference
}()
