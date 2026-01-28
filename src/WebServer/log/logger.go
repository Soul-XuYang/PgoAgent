package log

import (
	"os"
	"sync"
	"go.uber.org/zap"
	"go.uber.org/zap/zapcore"
	"strings"
	"fmt"
)

var (
	logger   *zap.Logger
	initOnce sync.Once //确保只执行一次
	initErr  error // 初始化错误
	validLevels = map[string]zapcore.Level{
    "debug":   zapcore.DebugLevel,
    "info":    zapcore.InfoLevel,
    "warn":    zapcore.WarnLevel,
    "error":   zapcore.ErrorLevel,
    "dpanic":  zapcore.DPanicLevel,
    "panic":   zapcore.PanicLevel,
    "fatal":   zapcore.FatalLevel,
    }
)
func getLevel(levelStr string) (zapcore.Level) {
    level, exists := validLevels[strings.ToLower(levelStr)] // 转换为小写
    if !exists {
        fmt.Printf("Warning: Invalid log level: %s. Defaulting to INFO\n", levelStr)
        return zapcore.InfoLevel
    }
    return level
}

// Init 初始化日志 prod 环境下使用生产日志配置，dev 环境下使用开发日志配置
// levelStr 日志级别 DEBUG INFO WARN ERROR
func Init(prod bool, levelStr string) error {
	initOnce.Do(func() {
		// 基础配置（dev / prod）
		var base zap.Config
		if prod {
			base = zap.NewProductionConfig() // 生产环境
		} else {
			base = zap.NewDevelopmentConfig()  // 开发环境
			base.EncoderConfig.EncodeCaller = zapcore.ShortCallerEncoder
		}
        
		level := getLevel(levelStr)
        base.Level.SetLevel(level) 

		enc := base.EncoderConfig
		enc.TimeKey = "timestamp"
		enc.EncodeTime = zapcore.TimeEncoderOfLayout("2006-01-02 15:04:05")
		enc.EncodeLevel = zapcore.CapitalLevelEncoder

		// 两个独立副本：一个不输出 caller，一个输出 caller
		encNoCaller := enc
		encNoCaller.CallerKey = ""

		encWithCaller := enc
		encWithCaller.CallerKey = "caller"

		var encA, encB zapcore.Encoder
		if prod {
			encA = zapcore.NewJSONEncoder(encNoCaller)
			encB = zapcore.NewJSONEncoder(encWithCaller)
		} else {
			encA = zapcore.NewConsoleEncoder(encNoCaller)
			encB = zapcore.NewConsoleEncoder(encWithCaller)
		}

		ws := zapcore.Lock(zapcore.AddSync(os.Stdout))

		coreNoCaller := zapcore.NewCore(encA, ws, zap.LevelEnablerFunc(func(l zapcore.Level) bool {
			return l < zapcore.ErrorLevel
		}))
		coreWithCaller := zapcore.NewCore(encB, ws, zap.LevelEnablerFunc(func(l zapcore.Level) bool {
			return l >= zapcore.ErrorLevel
		}))

		l := zap.New(
			zapcore.NewTee(coreNoCaller, coreWithCaller),
			zap.AddCaller(),      // 收集 caller 信息
			zap.AddCallerSkip(1), // 因为我们通过 log.L() 返回 logger，跳过 1 帧以定位真实调用方
			zap.AddStacktrace(zapcore.ErrorLevel),
		)

		logger = l //赋值给全局变量
	})

	return initErr
}

func L() *zap.Logger {  // 返回全局的 logger指针
	if logger == nil {
		_ = Init(false, "DEBUG")
	}
	return logger
}

// Sync 刷新缓冲（若未初始化则啥也不做）-确保所有日志
func Sync() error {
	if logger == nil {
		return nil
	}
	return logger.Sync() //logger.Sync() 的作用就是确保日志同步写入
}
