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
	AnimatedBanner()
	if LoadErr != nil {
		log.Fatalf("load config failed: %v", LoadErr)
	}
	if LoadEnvErr != nil {
		log.Fatalf("load env failed: %v", LoadEnvErr)
	}

	// 使用配置：拼接地址（注意 net.JoinHostPort 需要 string 端口）,Iota将数字转换字符串
	client_addr := net.JoinHostPort(ConfigHandler.WEBSERVER.Config.Host, strconv.Itoa(ConfigHandler.WEBSERVER.Config.Port)) 
	server_addr := net.JoinHostPort(ConfigHandler.GRPC.Server.Host, strconv.Itoa(ConfigHandler.GRPC.Server.Port))
	fmt.Println("web_server_addr:", client_addr)
	fmt.Println("web_server_timeout:", ConfigHandler.WEBSERVER.Config.Timeout)
	fmt.Println("grpc server addr:", server_addr)
	fmt.Println("version:", ConfigHandler.VERSION)
	fmt.Println("DSN:", EnvConfigHandler.DSN)
	fmt.Println("JWT_TOKEN:", EnvConfigHandler.JWTToken)
}	