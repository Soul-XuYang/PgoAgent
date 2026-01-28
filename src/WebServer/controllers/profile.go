package controllers

import (
	"net/http"
	"time"

	"github.com/gin-gonic/gin"
)

type UserInfo struct {
	Password string `json:"password"`
	Date     string `json:"date"`
	Weekday  string `json:"weekday"`
	Username string `json:"user_name"`
}

var weekdays = []string{"星期日", "星期一", "星期二", "星期三", "星期四", "星期五", "星期六"}

// GetInfo godoc
// @Summary     获取当前登录用户的基础信息
// @Tags        Profile
// @Security    BearerAuth
// @Produce     json
// @Success     200  {object}  UserInfo
// @Failure     401  {object}  map[string]string
// @Router      /profile [get]
// GetInfo GET请求 - 返回当前用户的基础信息（供前端展示用户名、日期等）
func GetInfo(c *gin.Context) {
	// 从上下文获取用户ID
	userID, exists := c.Get("user_id")
	if !exists {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "Unauthorized"})
		return
	}
	now := time.Now()
	userName, _ := c.Get("user_name")
	c.JSON(http.StatusOK, &UserInfo{
		Username: userName.(string),
		Date:     now.UTC().Format(time.RFC3339), //RFC3339格式
		Weekday:  weekdays[now.Weekday()],
		Password: userID.(string)})
}
