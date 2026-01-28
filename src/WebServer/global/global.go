package global

import (
	"PgoAgent/utils"
	"time"

    "PgoAgent/services" 
	"gorm.io/gorm"
)

var (
	DB           *gorm.DB
	FetchTimeout = 5 * time.Minute //对话超时
	UserCache  = utils.NewLocalCache(3 * time.Hour) //构建用户缓存
    GRPCClient *services.Client // 设置一个gRPC客户端
	GRPCTOKEN  string
)
