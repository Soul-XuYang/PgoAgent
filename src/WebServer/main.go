package main

import (
	"PgoAgent/config"
	"PgoAgent/global"
	"PgoAgent/log"
	"PgoAgent/router"
	"github.com/gin-gonic/gin"
	"go.uber.org/zap"
)

func main() {
	// 初始化日志
	if err := log.Init(false, "debug"); err != nil {
		panic(err)
	}
	defer log.Sync()
	monitor := log.NewMonitor()
	monitor.Start("../../") // 启动监控
	if config.LoadErr != nil || config.LoadEnvErr != nil {
		log.L().Error("Failed to load config or env config,got error:", zap.Error(config.LoadErr), zap.Error(config.LoadEnvErr))
	}
	config.Init()                   // 初始化配置
	defer global.GRPCClient.Close() //后续关闭客户端
	gin.SetMode(gin.ReleaseMode)    // 设置gin的模式
	router.Run("DEBUG")             
}
