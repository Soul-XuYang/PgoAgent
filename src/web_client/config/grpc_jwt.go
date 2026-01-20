package config
// 这里是对grpc的jwt进行封装，方便在其他地方使用
import (
	"context"
	"time"
	"github.com/golang-jwt/jwt/v5"
	"google.golang.org/grpc/metadata"
)

// JWTClaims JWT Claims 结构
type JWTClaims struct {
	UserID   string `json:"user_id"`
	UserName string `json:"user_name"`
	jwt.RegisteredClaims // 继承 jwt.RegisteredClaims-包含基本的jwt等元数据库
}

// GenerateJWTToken 生成 JWT Token
func GenerateJWTToken(userID string) (string, error) {
	// 从环境变量读取 JWT 密钥，如果加载失败则使用默认值
	jwtToken := "MY_SECRET_KEY"
	if EnvConfigHandler != nil && EnvConfigHandler.JWTToken != "" {
		jwtToken = EnvConfigHandler.JWTToken
	}

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

// WithJWTToken 将 JWT token 绑定到 context，返回新的 context,如果开启了JWT验证，则必须使用该函数
func WithJWTToken(ctx context.Context, userID string) (context.Context, error) {
	token, err := GenerateJWTToken(userID)
	if err != nil {
		return nil, err
	}
	// 使用grpc的metadata将token绑定到context
	return metadata.AppendToOutgoingContext(ctx, "authorization", "Bearer "+token), nil
}