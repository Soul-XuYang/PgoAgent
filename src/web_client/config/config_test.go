package config
import (
	"testing"
	"fmt"
	"log"
	"strconv"
	"net"
)
func  TestLoadConfig(t *testing.T) {
	fmt.Println("start load config")
	cfg, err := LoadConfig(ConfigPath)
	if err != nil {
		log.Fatalf("load config failed: %v", err)
	}

	// 使用配置：拼接地址（注意 net.JoinHostPort 需要 string 端口）
	addr := net.JoinHostPort(cfg.GRPC.Client.Host, strconv.Itoa(cfg.GRPC.Client.Port))
	fmt.Println("grpc client addr:", addr)
}