package controllers

import (
	// Client "PgoAgent/services"
	"context"
	"net/http"
	"time"

	"PgoAgent/global"
	"PgoAgent/log"
	"PgoAgent/models"
	"PgoAgent/services"
	"encoding/json"

	"fmt"

	"github.com/gin-gonic/gin"
	"github.com/google/uuid"
	"go.uber.org/zap"
	"gorm.io/gorm"
)

const (
	PAGE_SIZE    = 10
	TITLE_PROMT  = "请针对下述用户的问题，生成一个简洁明了的会话标题：\n用户输入："
	CHAT_TIMEOUT = 5 * time.Minute
	USER_ROLE    = "user"
	AI_ROLE      = "assistant"
)

// ConversationCreateRequest 首次发送消息时的请求体
type ConversationCreateRequest struct {
	ConversationID string `json:"conversation_id"`               // 前端可传已有会话ID，首条消息时可为空
	UserQuery      string `json:"user_query" binding:"required"` // 用户的首条消息内容
}

// ConversationCreateResponse 创建会话后的响应
type ConversationCreateResponse struct {
	ConversationID   string `json:"conversation_id"`
	ConversationName string `json:"conversation_name"`
}

// CreateConversations 创建会话并写入首条 user/assistant 消息 -创建以及包括第一个对话
func CreateConversations(c *gin.Context) {
	userID, exists := c.Get("user_id")
	if !exists {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "Unauthorized"})
		return
	}
	var req ConversationCreateRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	// 首次创建会话时，前端可以不传 conversation_id，这里自动生成
	if req.ConversationID == "" {
		req.ConversationID = uuid.New().String()
	}
	// 构建基本的上下文管理
	ctx, cancel := context.WithTimeout(context.Background(), CHAT_TIMEOUT)
	defer cancel() // 确保在函数结束时释放资源
	// 先调用后端大模型服务生成会话标题
	conversationResponse, err := global.GRPCClient.Chat(
		ctx,
		TITLE_PROMT+req.UserQuery,
		userID.(string),
		req.ConversationID,
	)
	if err != nil {
		log.L().Error("CreateConversations failed to generate conversation title", zap.Error(err))
		c.JSON(http.StatusInternalServerError, gin.H{"GRPC error": err.Error()})
		return
	}

	now := time.Now() //获取当前时间
	// 使用事务保证 会话 + 首条消息 一致性
	err = global.DB.Transaction(func(tx *gorm.DB) error { //gorm写对应的函数
		// 创建会话记录 -因为外键约束的操作，父表需要先创建- 后续加入到对应的事务队列里
		conversation := &models.Conversations{
			ID:               req.ConversationID,
			ConversationName: conversationResponse.Reply,
			UserID:           userID.(string),
		}
		if err := tx.Create(conversation).Error; err != nil {
			return err
		}
		// 写入首条 user 消息
		userMsg := &models.Messages{
			ConversationID: req.ConversationID,
			Role:           USER_ROLE,
			Content:        req.UserQuery,
			CreatedAt:      now,
		}
		if err := tx.Create(userMsg).Error; err != nil {
			return err
		}

		// 写入 assistant 回复消息（这里暂用标题作为内容，如果你有真正回复可以替换）
		assistantMsg := &models.Messages{
			ConversationID: req.ConversationID,
			Role:           AI_ROLE,
			Content:        conversationResponse.Reply,
			CreatedAt:      now,
		}
		if err := tx.Create(assistantMsg).Error; err != nil {
			return err
		}

		// 更新会话的最后一条消息信息
		conversation.LastMessageID = &assistantMsg.ID
		conversation.LastMsgTime = &assistantMsg.CreatedAt

		if err := tx.Model(conversation).
			Select("last_message_id", "last_msg_time"). //更新表的列
			Updates(conversation).Error; err != nil {
			return err
		}

		return nil
	})

	if err != nil {
		log.L().Error("Failed to create conversation with first messages", zap.Error(err))
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to create conversation"})
		return
	}
	fmt.Println("ok! ", conversationResponse.Reply)
	c.JSON(http.StatusCreated, &ConversationCreateResponse{
		ConversationID:   req.ConversationID,
		ConversationName: conversationResponse.Reply,
	})
}

// 核心对话函数

type SendMessageRequest struct {
	Content  string `json:"content" binding:"required"`
	Chatmode string `json:"chat_mode" binding:"required,oneof=stream invoke"`
}

type InvokeMessageResponse struct {
	Response   string    `json:"response"` //完整的响应
	CreatedAt  time.Time `json:"created_at"`
	TokenUsage int32     `json:"token_usage"`
}

type StreamMessageResponse struct {
	Content    string    `json:"content,omitempty"`
	Final      bool      `json:"final,omitempty"`
	CreatedAt  time.Time `json:"created_at,omitempty"`
	TokenUsage int32     `json:"token_usage,omitempty"`
}

// POST /api/v1/conversations/:id/messages //POST-这个是已有的对话ID下继续发消息
func SendMessage(c *gin.Context) {
	userID, exists := c.Get("user_id")
	if !exists {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "Unauthorized"})
		return
	}
	convID := c.Param("id")
	var req SendMessageRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}
	// 判断 chatmode
	switch req.Chatmode {
	case "invoke": //invoke模式
		HandleInvokeChat(c, userID.(string), convID, req.Content)
		log.L().Info("Invoke mode is successful!")
		return

	case "stream": //stream模式
		HandleStreamChat(c, userID.(string), convID, req.Content)
		log.L().Info("Stream mode is successful!")
		return
	default:
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid chatmode"})
	}
}

func HandleInvokeChat(c *gin.Context, userID string, conversationID string, input string) {
	var conv models.Conversations
	if err := global.DB.Where("id = ? AND user_id = ?", conversationID, userID).First(&conv).Error; err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "this conversation has not found"})
		return
	}
	// 数据库中先写入 user 消息
	now := time.Now()
	userMsg := &models.Messages{
		ConversationID: conversationID,
		Role:           USER_ROLE,
		Content:        input,
		CreatedAt:      now,
	}
	// 调 gRPC 拿 AI 回复
	ctx, cancel := context.WithTimeout(c.Request.Context(), CHAT_TIMEOUT)
	defer cancel()
	response, err := global.GRPCClient.Chat(ctx, input, userID, conversationID)
	if err != nil {
		log.L().Error("SendMessage chat error", zap.Error(err))
		c.JSON(http.StatusInternalServerError, gin.H{"error": "chat failed"})
		return
	}
	//
	lastTime := time.Now()
	// 在事务里写 user + assistant + 更新 LastMessageID/Time
	err = global.DB.Transaction(func(tx *gorm.DB) error {
		// 先写入user消息
		if err := tx.Create(userMsg).Error; err != nil {
			return err
		}
		// 再写入ai消息
		assistantMsg := &models.Messages{
			ConversationID: conversationID,
			Role:           AI_ROLE,
			Content:        response.Reply,
			CreatedAt:      lastTime,
		}
		if err := tx.Create(assistantMsg).Error; err != nil {
			return err
		}
		conv.LastMessageID = &assistantMsg.ID
		conv.LastMsgTime = &assistantMsg.CreatedAt
		//最后更新对话的时间和ID
		return tx.Model(&conv).
			Select("last_message_id", "last_msg_time").
			Updates(&conv).Error
	})
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "save message failed"})
		return
	}
	// 非流式模式直接返回
	c.JSON(http.StatusOK, &InvokeMessageResponse{
		Response:   response.Reply,
		CreatedAt:  lastTime,
		TokenUsage: response.TokenUsage, // 看你的 gRPC 返回
	})

}

// SSE模式 - 流式对话方式
func HandleStreamChat(c *gin.Context, userID string, conversationID string, input string) {
	var conv models.Conversations
	if err := global.DB.Where("id = ? AND user_id = ?", conversationID, userID).First(&conv).Error; err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "this conversation has not found"})
		return
	} //校验
	user_now := time.Now()
	if err := global.DB.Create(&models.Messages{
		ConversationID: conversationID,
		Role:           USER_ROLE, // 用户角色
		Content:        input,     // 用户的对话输入
		CreatedAt:      user_now,
	}).Error; err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "save user message failed"})
		return
	}
	//创建用户输入

	// 设置 SSE / 流式响应头
	w := c.Writer // 获取gin写入头
	flusher, ok := w.(http.Flusher)
	if !ok {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "streaming unsupported"})
		return
	}
	// 设置请求头
	w.Header().Set("Content-Type", "text/event-stream")
	w.Header().Set("Cache-Control", "no-cache") // 无缓存
	w.Header().Set("Connection", "keep-alive")  //长连接
	// 对某些反向代理禁止缓冲（按需）
	w.Header().Set("X-Accel-Buffering", "no") // 禁用缓冲
	c.Status(http.StatusOK)                   //提前设置

	// 调用stream GRPC函数
	ctx, cancel := context.WithTimeout(c.Request.Context(), CHAT_TIMEOUT)
	defer cancel()
	var (
		fullContent string
		chunk       = &StreamMessageResponse{} //提前创建好空间，指针传入数据
	)
	err := global.GRPCClient.ChatStream(
		ctx,
		input,
		userID,
		conversationID,
		// 处理所需的数据，每个数据片就是StreamChunk
		func(ch *services.StreamChunk) error {
			if ch.Output != "" {
				fullContent += ch.Output

				//这里流式返回的是最后一个才给token
				if !ch.FinalResponse {
					chunk = &StreamMessageResponse{ //响应的数据片
						Content: ch.Output,
						Final:   false, // 这里只负责增量展示，最后的 final 另发一条
					}
				} else {
					//如果是最终回复
					chunk = &StreamMessageResponse{ //响应的数据片
						Content:    ch.Output,
						TokenUsage: ch.Token, //这有最后一个才给token，因为这里是Langgraph节点传输
						Final:      true,     // 这里只负责增量展示，最后的 final 另发一条
					}

				}
				b, _ := json.Marshal(*chunk)
				fmt.Fprintf(w, "data: %s\n\n", b) //写入响应
				flusher.Flush()                   //弹出响应
			}

			return nil
		},
	)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "stream chat failed"})
		log.L().Error("StreamChat RPC failed", zap.Error(err))
		return
	}

	// 流结束后，创建消息信息和更新会话参数
	var assistantMsg models.Messages
	err = global.DB.Transaction(func(tx *gorm.DB) error {
		assistantMsg = models.Messages{
			ConversationID: conversationID,
			Role:           AI_ROLE,
			Content:        fullContent,
			CreatedAt:      time.Now(),
		}
		if err := tx.Create(&assistantMsg).Error; err != nil {
			return err
		}

		return tx.Model(&models.Conversations{}).
			Where("id = ?", conversationID).
			Updates(map[string]interface{}{
				"last_message_id": assistantMsg.ID,
				"last_msg_time":   assistantMsg.CreatedAt,
			}).Error
	})
	if err != nil {
		log.L().Error(" failed to save message or update conversation", zap.Error(err))
		return
	}

}
