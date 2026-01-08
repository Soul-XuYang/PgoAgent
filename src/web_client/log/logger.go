package log

import (
	"os"
	"sync"

	"go.uber.org/zap"
	"go.uber.org/zap/zapcore"
)

var (
	logger   *zap.Logger
	initOnce sync.Once
	initErr  error // 初始化错误
)

// Init 初始化 logger；多次调用是幂等的（只会第一次生效）
func Init(prod bool) error {
	initOnce.Do(func() {
		// 基础配置（dev / prod）
		var base zap.Config
		if prod {
			base = zap.NewProductionConfig()
		} else {
			base = zap.NewDevelopmentConfig()
			base.EncoderConfig.EncodeCaller = zapcore.ShortCallerEncoder
		}

		// 复制一份 EncoderConfig，后续对其副本进行不同修改
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

		// 输出到 stdout（需要时可替换为文件或滚动 writer）
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

		logger = l
	})

	return initErr
}

func L() *zap.Logger {  // 返回全局的 logger指针
	if logger == nil {
		_ = Init(false)
	}
	return logger
}

// Sync 刷新缓冲（若未初始化则啥也不做）-确保所有日志心如
func Sync() error {
	if logger == nil {
		return nil
	}
	return logger.Sync() //logger.Sync() 的作用就是确保日志同步写入
}
