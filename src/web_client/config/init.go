package config

import (
	"PgoAgent/global"
	"PgoAgent/log"
	"PgoAgent/models"
	"PgoAgent/services"
	"fmt"

	"go.uber.org/zap"
)

const (
	defaultUserID       = "user001"
	defaultUserName     = "admin"
	defaultUserPassword = "123456"
	DeBug               = true
)
const (
	KB = 1024
	MB = 1024 * 1024
	GB = 1024 * 1024 * 1024
	TB = 1024 * 1024 * 1024 * 1024
)

func initDefaultUser() error {
	// 使用Count代替First，避免record not found日志
	var count int64
	err := global.DB.Model(&models.Users{}).Where("id = ?", defaultUserID).Count(&count).Error
	if err != nil {
		return fmt.Errorf("failed to check user existence: %v", err)
	}
	if count > 0 {
		// 用户已存在，无需创建初始化了
		return nil
	}
	// 创建默认用户
	defaultUser := models.Users{
		ID:       defaultUserID,
		Username: defaultUserName,
		Password: defaultUserPassword,
		Role:     "admin",
	}

	if err := global.DB.Create(&defaultUser).Error; err != nil {
		return fmt.Errorf("failed to create default user: %v", err)
	}

	return nil
}
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
	if DeBug {
		err := initDefaultUser()
		if err != nil {
			log.L().Fatal("Failed to init default user, got error:", zap.Error(err))
		}
	}
	initGRPCClient()
}
