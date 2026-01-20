package log

import (
	"PgoAgent/utils"
	"context"
	"fmt"
	"path/filepath"
	"time"

	"go.uber.org/zap"
)

const defaultInterval = 1 * time.Hour

type Monitor struct {
	ctx       context.Context
	cancel    context.CancelFunc
	startTime time.Time
	interval  time.Duration
}

// NewMonitor 创建并返回一个新的Monitor实例
func NewMonitor() *Monitor { //
	ctx, cancel := context.WithCancel(context.Background()) //基于一个父context创建一个新的可取消的context-设置根节点无限制
	return &Monitor{
		ctx:       ctx,
		cancel:    cancel,
		startTime: time.Now(),
		interval:  defaultInterval,
	}
}
func (m *Monitor) Stop() {
	m.cancel() // 执行这个取消函数
}

// Start 启动监控程序，path为项目根目录，实际为代码历史的保存目录
func (m *Monitor) Start(path string) { // 开启一个新的线程
	go func() { // 开启一个新的线程
		ticker := time.NewTicker(m.interval) // 创建定时计数器
		defer ticker.Stop()                  // 最后程序要停止
		gitignore, err := utils.NewGitIgnore(filepath.Join(path, ".gitignore"))
		if err != nil {
			L().Warn("Failed to load .gitignore, fallback to default ignore list", zap.Error(err))
		}
		code_counter := utils.NewCodeCounter()
		if err := code_counter.Analyze(path, gitignore); err != nil {
			L().Error("Code files analysis failed", zap.Error(err))
			return
		}
		time.Sleep(2 * time.Second)
		code_counter.PrintReport()

		for {
			select { //通过ctx控制何时停止
			case <-ticker.C:
				elapsed := time.Since(m.startTime)
				days := int(elapsed.Hours()) / 24
				hours := int(elapsed.Hours()) % 24
				L().Info(fmt.Sprintf("当前程序已运行: %d天%02d小时", days, hours))
			case <-m.ctx.Done(): // m.ctx.Done()也是一个channel，当context被取消时会收到值
				elapsed := time.Since(m.startTime)
				days := int(elapsed.Hours()) / 24
				hours := int(elapsed.Hours()) % 24
				minutes := int(elapsed.Minutes()) % 60
				seconds := int(elapsed.Seconds()) % 60
				L().Info(fmt.Sprintf("监控程序已停止,共运行: %d天 %02d小时 %02d分钟 %02d秒", days, hours, minutes, seconds))
				return
			}
		}
	}()
}
