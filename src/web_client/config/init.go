package config

import (
	"PgoAgent/global"
	"PgoAgent/log"
	"PgoAgent/services"
	"fmt"

	"go.uber.org/zap"
)


const (
	KB = 1024
	MB = 1024 * 1024
	GB = 1024 * 1024 * 1024
	TB = 1024 * 1024 * 1024 * 1024
)


func initGRPCClient() {
	client, err := services.NewClient(ConfigHandler.GRPC.Server.Host, ConfigHandler.GRPC.Server.Port, ConfigHandler.GRPC.Server.SendSize*MB, ConfigHandler.GRPC.Server.ReceiveSize*MB)
	if err != nil {
		log.L().Fatal("Failed to create gRPC client, got error:", zap.Error(err))
		panic(err)
	}
	global.GRPCClient = client
	fmt.Println("3. gRPC client initialized successfully")
}

func Init() {
	SimpleBanner()
	if LoadErr != nil {
		log.L().Fatal("Failed to load config.toml, got error:", zap.Error(LoadErr))
		panic(LoadErr)
	}
	if LoadEnvErr != nil {
		log.L().Fatal("Failed to load .env, got error:", zap.Error(LoadEnvErr))
		panic(LoadEnvErr)
	}
	initDB()
	dbMigrate()
	initGRPCClient()
}
