package config

import (
	"os"
	"path/filepath"
	"runtime"
	"time"

	"github.com/BurntSushi/toml"
	"github.com/joho/godotenv"
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
	GRPC      GRPCConfig `toml:"agent"`
	VERSION   string     `toml:"version"`
	WEBSERVER WebServer  `toml:"web"`
}

type GRPCConfig struct {
	Server GRPCServerConfig `toml:"server"`
}

type GRPCServerConfig struct {
	Host        string `toml:"host"`
	Port        int    `toml:"port"`
	SendSize    int    `toml:"send_size"`    
	ReceiveSize int    `toml:"receive_size"` 
}

type WebServer struct {
	Config WebServerConfig `toml:"server"`
}
type WebServerConfig struct {
	Host    string `toml:"host"`
	Port    int    `toml:"port"`
	Timeout int    `toml:"timeout"`
	MaxIdleConns int `toml:"max_idle_conns"`
	MaxOpenConns int `toml:"max_open_conns"`
	ConnMaxLifetime int `toml:"conn_max_lifetime_hours"` // 连接最大生命周期（小时）
}

type EnvConfig struct {
    DSN string `toml:"DATABASE_URL"`
	JWTToken string `toml:"JWT_TOKEN"`
	WEBToken string `toml:"WEB_TOKEN"`
}
// 这里用path传入是因为公共的数据节省内存
func LoadEnv()(*EnvConfig,error) {
	_, filename, _, _ := runtime.Caller(0)
	dir := filepath.Dir(filename)
	EnvPath:= filepath.Join(dir, "..", "..", "..", ".env")
	if  err := godotenv.Load(EnvPath); err != nil {
		return nil,err
	}
	// 加载环境变量
    JWTToken := os.Getenv("GRPC_TOKEN")
	WEBToken := os.Getenv("WEB_TOKEN")
	if JWTToken == "" {
		JWTToken = "MY_SECRET_KEY"
	}
	if WEBToken == "" {
		WEBToken = "MY_SECRET_KEY"
	}
	return &EnvConfig{
		DSN: os.Getenv("DATABASE_URL"),
		JWTToken: JWTToken,
		WEBToken: WEBToken,
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
