package controllers

import (
	"errors"
	"net/http"
	"time"

	"PgoAgent/global"
	"PgoAgent/log"

	"github.com/gin-gonic/gin"
	"go.uber.org/zap"
	"gorm.io/datatypes"
	"gorm.io/gorm"
)

// 这里是用户长期记忆存储的命名空间和键名
const (
	// StoreNamespaceRoot 存储命名空间根
	StoreNamespaceRoot = "user_memory"
	// StoreKey 存储键名
	StoreKey = "profile"
)

// namespaceForUser: 生成与 Python/langgraph 一致的 prefix
// 例如: user_id = "user_003" -> prefix = "user_memory.user_003"
func namespaceForUser(userID string) string {
	return StoreNamespaceRoot + "." + userID
}

// Store: langgraph 创建的 store 表结构，无需迁移创建
type Store struct {
	Prefix    string         `gorm:"column:prefix;type:text;primaryKey"`
	Key       string         `gorm:"column:key;type:text;primaryKey"`
	Value     datatypes.JSON `gorm:"column:value;type:jsonb"`
	CreatedAt time.Time      `gorm:"column:created_at"`
	UpdatedAt time.Time      `gorm:"column:updated_at"`
	ExpiresAt *time.Time     `gorm:"column:expires_at"`
	TTLMin    *int           `gorm:"column:ttl_minutes"`
}

// 显式指定表名为 store（与你数据库里的 public.store 对应）
func (Store) TableName() string {
	return "store"
}

// StoreItem: 只读 value 和 updated_at 的精简结构
type StoreItem struct {
	Value     datatypes.JSON `json:"value" gorm:"column:value;type:jsonb"`
	UpdatedAt time.Time      `json:"updated_at" gorm:"column:updated_at"`
}

// GetUserLongTermMemory godoc
// @Summary     获取当前用户的长期记忆
// @Tags        Memory
// @Security    BearerAuth
// @Produce     json
// @Success     200  {object}  StoreItem
// @Failure     401  {object}  map[string]string
// @Failure     404  {object}  map[string]string
// @Failure     500  {object}  map[string]string
// @Router      /profile/store [get]
// GetUserLongTermMemory 获取当前用户的长期记忆
func GetUserLongTermMemory(c *gin.Context) {
	userID, exists := c.Get("user_id")
	if !exists {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "Unauthorized"})
		return
	}

	ctx := c.Request.Context()
	userIDStr := userID.(string)
	prefix := namespaceForUser(userIDStr)

	var item StoreItem
	if err := global.DB.WithContext(ctx).
		Model(&Store{}).
		Select("value", "updated_at").
		Where(`prefix = ? AND "key" = ?`, prefix, StoreKey).
		Take(&item).Error; err != nil {

		// 如果记录不存在，返回404-易遗忘
		if errors.Is(err, gorm.ErrRecordNotFound) {
			c.JSON(http.StatusNotFound, gin.H{"error": "long term memory not found"})
			return
		}

		log.L().Error("Failed to get user long term memory", zap.Error(err))
		log.L().Error("Failed to get user long term memory", zap.Error(err))
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to load user's long memory"})
		return
	}

	c.JSON(http.StatusOK, item)
}

// SetUserLongTermMemoryRequest 设置长期记忆的请求体
type SetUserLongTermMemoryRequest struct {
	Value datatypes.JSON `json:"value"` // 这里是用户长期记忆，需要前端以 json 包装
}

// SetUserLongTermMemory godoc
// @Summary     设置或更新当前用户的长期记忆
// @Tags        Memory
// @Security    BearerAuth
// @Accept      json
// @Produce     json
// @Param       data  body      SetUserLongTermMemoryRequest  true  "长期记忆内容(JSON)"
// @Success     200   {object}  map[string]string
// @Failure     400   {object}  map[string]string
// @Failure     401   {object}  map[string]string
// @Failure     500   {object}  map[string]string
// @Router      /profile/store [post]
// SetUserLongTermMemory 更新当前用户的长期记忆（仅更新 value / updated_at）
func SetUserLongTermMemory(c *gin.Context) {
	userID, exists := c.Get("user_id")
	if !exists {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "Unauthorized"})
		return
	}

	var req SetUserLongTermMemoryRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid request body"})
		return
	}

	prefix := namespaceForUser(userID.(string))
	now := time.Now()
	ctx := c.Request.Context()

	// 这里只做 UPDATE，不做插入；如果可能不存在，可以再加一层 Upsert 逻辑
	if err := global.DB.WithContext(ctx).
		Model(&Store{}).
		Where(`prefix = ? AND "key" = ?`, prefix, StoreKey).
		Updates(map[string]any{
			"value":      req.Value,
			"updated_at": now,
		}).Error; err != nil {

		log.L().Error("Failed to set user's long term memory", zap.Error(err))
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to save user's long memory"})
		return
	}

	c.JSON(http.StatusOK, gin.H{"message": "User's long term memory updated successfully"})
}

// DeleteUserLongTermMemory godoc
// @Summary     删除当前用户的长期记忆
// @Tags        Memory
// @Security    BearerAuth
// @Produce     json
// @Success     200  {object}  map[string]string
// @Failure     401  {object}  map[string]string
// @Failure     500  {object}  map[string]string
// @Router      /profile/store [delete]
// DeleteUserLongTermMemory 删除当前用户的长期记忆
func DeleteUserLongTermMemory(c *gin.Context) {
	userID, exists := c.Get("user_id")
	if !exists {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "Unauthorized"})
		return
	}

	prefix := namespaceForUser(userID.(string))
	ctx := c.Request.Context()

	if err := global.DB.WithContext(ctx).
		Where(`prefix = ? AND "key" = ?`, prefix, StoreKey).
		Delete(&Store{}).Error; err != nil {
		log.L().Error("Failed to delete user's long term memory", zap.Error(err))
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to delete user's long memory"})
		return
	}

	c.JSON(http.StatusOK, gin.H{"message": "User's long term memory deleted successfully"})
}
