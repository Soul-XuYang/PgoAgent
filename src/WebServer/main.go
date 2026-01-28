package main

import (
	"PgoAgent/config"
	"PgoAgent/global"
	"PgoAgent/log"
	"PgoAgent/router"
	"github.com/gin-gonic/gin"
	"go.uber.org/zap"

	_ "PgoAgent/docs" // 引入自动生成的文档
)

// @title           PgoAgent Web API
// @version         0.0.3
// @description     PgoAgent 的 Web 客户端接口文档
// @BasePath        /api/v1  基础路径前缀

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
