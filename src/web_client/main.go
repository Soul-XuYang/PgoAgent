package main

import (
	"PgoAgent/log"
    "PgoAgent/config"
	"time"
)

func main() {
	// 初始化日志
	if err := log.Init(false); err != nil {
		panic(err)
	}
	defer log.Sync()
    config.SimpleBanner()
	monitor := log.NewMonitor()
	monitor.Start("../../") // 启动监控
    time.Sleep(10 * time.Second)
}
