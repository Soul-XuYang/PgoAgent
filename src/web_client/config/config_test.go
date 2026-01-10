package config
import (
	"testing"
	"fmt"
	"log"
	"strconv"
	"net"
)
func  TestLoadConfig(t *testing.T) {
	fmt.Println("start load config!")
	cfg, err := LoadConfig(ConfigPath)
	if err != nil {
		log.Fatalf("load config failed: %v", err)
	}

	// 使用配置：拼接地址（注意 net.JoinHostPort 需要 string 端口）,Iota将数字转换字符串
	client_addr := net.JoinHostPort(cfg.WEBSERVER.Config.Host, strconv.Itoa(cfg.WEBSERVER.Config.Port)) 
	server_addr := net.JoinHostPort(cfg.GRPC.Server.Host, strconv.Itoa(cfg.GRPC.Server.Port))
	fmt.Println("web_server_addr:", client_addr)
	fmt.Println("web_server_timeout:", cfg.WEBSERVER.Config.Timeout)
	fmt.Println("grpc server addr:", server_addr)
	fmt.Println("version:", cfg.VERSION)

}	