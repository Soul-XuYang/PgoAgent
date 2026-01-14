package grpc_client

import (
	"time"
    "PgoAgent/config"
	"github.com/golang-jwt/jwt/v5"
)

// JWTClaims JWT Claims 结构
type JWTClaims struct {
	UserID   string `json:"user_id"`
	UserName string `json:"user_name"`
	jwt.RegisteredClaims // 继承 jwt.RegisteredClaims-包含基本的jwt等元数据库
}

// GenerateJWTToken 生成 JWT Token
func GenerateJWTToken(userID string) (string, error) {
	// 从环境变量读取 JWT 密钥
	jwtToken:= config.EnvConfigHandler.JWTToken

	// 创建 Claims
	claims := &JWTClaims{
		UserID:   userID,
		RegisteredClaims: jwt.RegisteredClaims{
			ExpiresAt: jwt.NewNumericDate(time.Now().Add(24 * time.Hour)), // 24小时过期,该请求
			IssuedAt:  jwt.NewNumericDate(time.Now()),
			NotBefore: jwt.NewNumericDate(time.Now()),
		},
	}

	// 生成 token
	token := jwt.NewWithClaims(jwt.SigningMethodHS256, claims)
	return token.SignedString([]byte(jwtToken)) // 签名并返回 token
}