package utils

import (
	"errors"
	"strings"
	"time"

	"github.com/golang-jwt/jwt/v5"
)

const (
	ExpireHours      = 24     //Token过期时间（小时）
	defaultRole      = "user" //这里留有对应的接口
	defaultSecretKey = "MY_SECRET_KEY"
)

func GenerateJWT(userID string, userName string, role string, tokenstr string) (string, error) {
	// 用 MapClaims 时，直接传入 jwt.MapClaims{...}
	claims := jwt.MapClaims{ // 这里是客户端的jwt设置 - 这里payload加载对应元数据
		"userID":   userID,
		"userName": userName,
		"role":     role,
		"exp":      time.Now().Add(time.Duration(ExpireHours) * time.Hour).Unix(), // 过期时间（秒）
		"iat":      time.Now().Unix(),                                             // 签发时间（可选）
		"nbf":      time.Now().Unix(),                                             // 生效时间（可选）
	}
	token := jwt.NewWithClaims(jwt.SigningMethodHS256, claims)
	// 生产环境：把 "secret" 放到配置/环境变量里
	if tokenstr == "" {
		tokenstr = defaultSecretKey
	}
	signedToken, err := token.SignedString([]byte(tokenstr))
	return "Bearer " + signedToken, err // 注意 Bearer 后面要有空格
}


// ParseJWT 解析 JWT token，返回 userID, userName, role, expireTime, error
func ParseJWT(tk string, tokenstr string) (string, string, string, error) {
    parts := strings.Split(tk, " ")
    if len(parts) == 2 && parts[0] == "Bearer" {
        tk = parts[1]
    }
    if tokenstr == "" {
        tokenstr = defaultSecretKey
    }

    token, err := jwt.Parse(tk, func(token *jwt.Token) (interface{}, error) {
        if _, ok := token.Method.(*jwt.SigningMethodHMAC); !ok {
            return nil, jwt.ErrTokenUnverifiable
        }
        return []byte(tokenstr), nil
    })

    if err != nil {
        return "", "", "", err
    }

    if claims, ok := token.Claims.(jwt.MapClaims); ok && token.Valid {
        userID, ok1 := claims["userID"].(string)
        userName, ok2 := claims["userName"].(string)
        role, ok3 := claims["role"].(string)

        if !ok1 {
            return "", "", "", errors.New("invalid userID claim")
        }
        if !ok2 {
            return "", "", "", errors.New("invalid userName claim")
        }
        if !ok3 {
            return "", "", "", errors.New("invalid role claim")
        }

        return userID, userName, role, nil
    }

    return "", "", "", errors.New("invalid token")
}


