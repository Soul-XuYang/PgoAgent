package main  // 声明主包，必须是main才能生成可执行程序

import (
    "fmt"
    "os"
    "Pgoagent/log"
    "go.uber.org/zap"
    "time"
    "path/filepath"
)   // 导入格式化输出的标准库

// main函数：程序的入口函数，必须是main()
func main() {
    	//初始化日志以及监控代码程序
	if err := log.Init(false); err != nil { // 初始化日志-false 表示开发模式
		panic(err)
	}
	defer log.Sync() //确保日志写入
	Monitor := log.NewMonitor()
	dir, err := os.Getwd()
    stastics_dir := filepath.Clean(filepath.Join(dir, "..", ".."))
	if err != nil {
		log.L().Error("Failed to get Path", zap.Error(err))
	}
    fmt.Println(stastics_dir)
	Monitor.StartMonitor(stastics_dir) // 这里输入的路径是项目根目录
	defer Monitor.StopMonitor()
    fmt.Println("Hello Go! 我的第一个Go项目")
    time.Sleep(10 * time.Second)
}