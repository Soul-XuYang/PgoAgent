package middlewares

import (
	"PgoAgent/config"
	"PgoAgent/utils"
	"net/http"

	"github.com/gin-gonic/gin"
)

// JWT认证组件
func JWTAuthMiddleware() gin.HandlerFunc { // 返回一个函数，该函数接收一个gin.Context参数
	return func(c *gin.Context) {
		// 从Cookie中获取token
		token, err := c.Cookie(utils.CookieName) //从cokie中的对应键名获取token
		if err != nil {
			// 如果Cookie中没有，尝试从Authorization header获取
			authHeader := c.GetHeader("Authorization")
			if authHeader == "" {
				c.JSON(http.StatusUnauthorized, gin.H{"error": "Unauthorized: missing token"})
				c.Abort()
				return
			}
			token = authHeader
		}

		// 解析JWT token
		userID, userName, role, err := utils.ParseJWT(token, config.WEBTOKEN) // 二者比较解析
		if err != nil {
			c.JSON(http.StatusUnauthorized, gin.H{"error": "Unauthorized: invalid token"})
			c.Abort()
			return
		}
		// 将用户信息存储到context中
		c.Set("user_id", userID)
		c.Set("user_name", userName)
		c.Set("user_role", role)
		c.Next()
	}
}
