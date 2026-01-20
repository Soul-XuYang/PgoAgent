package middlewares
import (
	"github.com/gin-gonic/gin"
    "go.uber.org/zap"
    "runtime/debug"
	"PgoAgent/log"
)
func GinRecovery() gin.HandlerFunc {
	return func(c *gin.Context) {
		defer func() {
			if err := recover(); err != nil {
				log.L().Error("panic recovered",
					zap.Any("error", err),                  // 存入错误信息
					zap.ByteString("stack", debug.Stack()), // 记录堆栈信息
					zap.String("method", c.Request.Method), //对应的HTTP返回的方法
					zap.String("path", c.Request.URL.Path), //对应的HTTP返回的路径
				)
				c.AbortWithStatusJSON(500, gin.H{"error": "InternalServer error"}) // 返回 500（最简单版）
			}
		}()
		c.Next()
	}
}