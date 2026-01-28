package controllers

import (
	"errors"
	"strings"

	"PgoAgent/global"
	"PgoAgent/models"
    "PgoAgent/utils"

	"github.com/gin-gonic/gin"
	"gorm.io/gorm"
    "net/http"
)

// DELETE /api/v1/conversations/:id
// 删除会话：同时删除 messages + langgraph checkpoint 相关记录

// @Summary      删除对话
// @Description  在认证后删除对应的对话的数据
// @Tags         User
// @Security     BearerAuth
// @Accept       json
// @Produce      json
// @Param        data  body      deleteInput  true  "User credentials"
// @Success      200   {object}  map[string]interface{}  "退出成功"
// @Failure      400   {object}  map[string]interface{}  "请求参数错误"
// @Failure      401   {object}  map[string]interface{}  "未认证"
// @Failure      500   {object}  map[string]interface{}  "服务器错误"
// @Router       /auth/delete/conversation/:id [delete]
func DeleteConversation(c *gin.Context) {
	userID, exists := c.Get("user_id")
	if !exists {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "Unauthorized"})
		return
	}

	conversationID := strings.TrimSpace(c.Param("id"))
	// 删除操作需要非常谨慎，这里先检查会话 ID 是否为空或非法
	if conversationID == "" || conversationID == "undefined" {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid conversation id"})
		return
	}

	tx := global.DB.Begin()

    defer func() {
        if r := recover(); r != nil {
            tx.Rollback()
            // 注意：如果你已经写过响应，这里再写可能重复。
            c.AbortWithStatusJSON(500, gin.H{"error": "Internal server error"})
        }
    }()

	// 先检查会话是否存在且属于当前用户（在事务里查）
	var conversation models.Conversations
	if err := tx.Where("id = ? AND user_id = ?", conversationID, userID).First(&conversation).Error; err != nil {
		tx.Rollback()
		if errors.Is(err, gorm.ErrRecordNotFound) {
			c.JSON(http.StatusNotFound, gin.H{"error": "Conversation not found"})
		} else {
			c.JSON(http.StatusInternalServerError, gin.H{"error": "Database error"})
		}
		return
	}

	// 1. 先删除业务侧的消息记录
	if err := tx.Where("conversation_id = ?", conversationID).
		Delete(&models.Messages{}).Error; err != nil {
		tx.Rollback()
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to delete this conversation's messages"})
		return
	}

	// 2. 删除 langgraph checkpoint 相关记录 -这里需要删除三个表的数据
	if err := tx.Exec(`DELETE FROM checkpoint_writes WHERE thread_id = ?`, conversationID).Error; err != nil {
        tx.Rollback()
        c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to delete checkpoint_writes"})
        return
    }
    if err := tx.Exec(`DELETE FROM checkpoint_blobs WHERE thread_id = ?`, conversationID).Error; err != nil {
        tx.Rollback()
        c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to delete checkpoint_blobs"})
        return
    }
    if err := tx.Exec(`DELETE FROM checkpoints WHERE thread_id = ?`, conversationID).Error; err != nil {
        tx.Rollback()
        c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to delete checkpoints"})
        return
    }
	// 3. 最后删除会话本身
	if err := tx.Delete(&conversation).Error; err != nil {
		tx.Rollback()
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to delete conversation"})
		return
	}

	// 提交事务
	if err := tx.Commit().Error; err != nil {
		c.JSON(http.StatusOK, gin.H{"error": "Failed to commit transaction"})
		return
	}

	c.JSON(200, gin.H{"message": "Conversation deleted successfully"})
}


// 删除用户也是一个非常 carefully 的操作：这里可见python中的存储节点的操作
// 本质是一个命名空间+key-value哈希表的操作，故而我们需要删除命名空间即可删除用户数据

// @Summary      删除用户
// @Description  在认证后删除对应的用户的数据
// @Tags         User
// @Security     BearerAuth
// @Accept       json
// @Produce      json
// @Param        data  body      deleteInput  true  "User credentials"
// @Success      200   {object}  map[string]interface{}  "退出成功"
// @Failure      400   {object}  map[string]interface{}  "请求参数错误"
// @Failure      401   {object}  map[string]interface{}  "未认证"
// @Failure      500   {object}  map[string]interface{}  "服务器错误"
// @Router       /auth/delete [delete]
// 这个是在登录之后的注销页面
func DeleteUser(c *gin.Context) {
	userID, exists := c.Get("user_id")
	if !exists {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "Unauthorized"})
		return
	}
	userIDStr, ok := userID.(string)
	if !ok || userIDStr == "" {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "Unauthorized"})
		return
	}
	var deleteInput deleteInput //获得其请求的数据
	if err := c.ShouldBindJSON(&deleteInput); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}
	var user models.Users //获得其用户模型信息
	if err := global.DB.Model(&models.Users{}).Where("id = ?", userIDStr).First(&user).Error; err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to retrieve user"})
		return
	}

	if !CheckPassword(user.Password, deleteInput.Password) || user.Username != deleteInput.Username {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "Invalid password"})
		return
	}
	if err := global.DB.Delete(&user).Error; err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to delete user"})
		return
	}
	global.UserCache.Delete(user.Username) // 清理对应的用户
	utils.ClearAuthCookie(c)
	c.JSON(http.StatusOK, gin.H{
		"ok": true,
	})
}