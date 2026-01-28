package controllers

import (
	// Client "PgoAgent/services"
	"context"
	"net/http"
	"time"

	"PgoAgent/config"
	"PgoAgent/global"
	"PgoAgent/log"
	"PgoAgent/models"
	"PgoAgent/services"
	"encoding/json"
	"fmt"
	"strconv"

	"github.com/gin-gonic/gin"
	"github.com/google/uuid"
	"go.uber.org/zap"
	"gorm.io/gorm"
)

const (
	PAGE_SIZE    = 20
	TITLE_PROMT  = "请针对下述用户的问题，生成一个简洁明了的对话标题，[要求]:无需标注直接输出即可：	\n用户输入:"
	FIRST_QUERY  = "回答上述用户的问题"
	CHAT_TIMEOUT = 5 * time.Minute
	USER_ROLE    = "user"
	AI_ROLE      = "assistant"
)

type Message struct {
	ID        string    `json:"id"`
	Role      string    `json:"role"`
	Content   string    `json:"content"`
	CreatedAt time.Time `json:"created_at"`
}

// ConversationCreateRequest 首次发送消息时的请求体
type ConversationCreateRequest struct {
	ConversationID string `json:"conversation_id"`               // 前端可传已有会话ID，首条消息时可为空
	UserQuery      string `json:"user_query" binding:"required"` // 用户的首条消息内容
}

// ConversationCreateResponse 创建会话后的响应
type ConversationCreateResponse struct {
	ConversationID   string    `json:"conversation_id"`
	ConversationName string    `json:"conversation_name"`
	Messages         []Message `json:"messages"`
}

// CreateConversations godoc
// @Summary     创建会话并写入首条消息
// @Tags        Conversations
// @Security    BearerAuth
// @Accept      json
// @Produce     json
// @Param       data  body      ConversationCreateRequest  true  "创建会话参数"
// @Success     201   {object}  ConversationCreateResponse
// @Failure     400   {object}  map[string]string
// @Failure     401   {object}  map[string]string
// @Failure     500   {object}  map[string]string
// @Router      /conversations [post]
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
	lastnow := time.Now()
	// 首次创建会话时，前端可以不传 conversation_id，这里自动生成
	if req.ConversationID == "" {
		req.ConversationID = uuid.New().String()
	}

	ctx, cancel := context.WithTimeout(context.Background(), CHAT_TIMEOUT)
	ctxWithToken, err := config.WithJWTToken(ctx, userID.(string)) // 添加GRPC的 JWT Token
	if err != nil {
		log.L().Error("failed to attach JWT token to gRPC context", zap.Error(err))
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to attach JWT token"})
		cancel()
		return
	}
	defer cancel()

	// 先调用后端大模型服务生成会话标题
	conversationTitle, err := global.GRPCClient.Chat(
		ctxWithToken,
		TITLE_PROMT+req.UserQuery,
		userID.(string),
		req.ConversationID,
	)
	conversationContent, err := global.GRPCClient.Chat(
		ctxWithToken,
		FIRST_QUERY,
		userID.(string),
		req.ConversationID,
	)
	if err != nil {
		log.L().Error("CreateConversations failed to generate conversation title, GRPC error:", zap.Error(err))
		c.JSON(http.StatusInternalServerError, gin.H{"GRPC error": err.Error()})
		return
	}

	now := time.Now() //获取当前时间
	// 使用事务保证 会话 + 首条消息 一致性
	err = global.DB.Transaction(func(tx *gorm.DB) error { //gorm写对应的函数
		// 创建会话记录 -因为外键约束的操作，父表需要先创建- 后续加入到对应的事务队列里
		conversation := &models.Conversations{
			ID:               req.ConversationID,
			ConversationName: conversationTitle.Reply,
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
			Content:        conversationContent.Reply,
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
	fmt.Println("ok! ", conversationContent.Reply)
	//初始化对应的内容
	c.JSON(http.StatusCreated, &ConversationCreateResponse{
		ConversationID:   req.ConversationID,
		ConversationName: conversationTitle.Reply,
		Messages: []Message{
			{
				Role:      USER_ROLE,
				Content:   req.UserQuery,
				CreatedAt: lastnow,
			},
			{
				Role:      AI_ROLE,
				Content:   conversationContent.Reply,
				CreatedAt: now,
			},
		},
	},
	)
}

// 核心对话模块
type SendMessageRequest struct {
	Content  string `json:"content" binding:"required"`
	Chatmode string `json:"chat_mode" binding:"required,oneof=stream invoke"`
}

type InvokeMessageResponse struct {
	Message    Message `json:"message"` //完整的响应
	TokenUsage int32   `json:"token_usage"`
}

// 流式的话单独发送不然难以处理，流式默认就是AI回复-易错
type StreamMessageResponse struct {
	Content    string    `json:"content,omitempty"`
	Final      bool      `json:"final,omitempty"`
	CreatedAt  time.Time `json:"created_at,omitempty"`
	TokenUsage int32     `json:"token_usage,omitempty"`
	NodeName   string    `json:"node_name,omitempty"` // 节点名称，用于前端判断是否是状态消息
}

// CancelResponse 取消对话任务的响应
type CancelResponse struct {
	Success bool   `json:"success"`
	Message string `json:"message"`
}

// SendMessage godoc
// @Summary     在已有会话下继续发送消息
// @Tags        Conversations
// @Security    BearerAuth
// @Accept      json
// @Produce     json
// @Param       id    path      string               true  "Conversation ID"
// @Param       data  body      SendMessageRequest   true  "发送消息参数"
// @Success     200   {object}  InvokeMessageResponse
// @Failure     400   {object}  map[string]string
// @Failure     401   {object}  map[string]string
// @Failure     404   {object}  map[string]string
// @Failure     500   {object}  map[string]string
// @Router      /conversations/{id}/messages [post]
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
	// 调 gRPC 拿 AI 回复，并为请求绑定 JWT token
	ctx, cancel := context.WithTimeout(context.Background(), CHAT_TIMEOUT)
	ctxWithToken, err := config.WithJWTToken(ctx, userID) // 添加GRPC的 JWT Token
	if err != nil {
		log.L().Error("failed to attach JWT token to gRPC context", zap.Error(err))
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to attach JWT token"})
		cancel()
		return
	}
	defer cancel()

	response, err := global.GRPCClient.Chat(ctxWithToken, input, userID, conversationID)
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
	// 非流式模式直接返回消息即可
	c.JSON(http.StatusOK, &InvokeMessageResponse{
		Message: Message{
			Role:      AI_ROLE,
			Content:   response.Reply,
			CreatedAt: lastTime,
		},

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

	// 调用 stream gRPC 函数，并为请求绑定 JWT token
	ctx, cancel := context.WithTimeout(context.Background(), CHAT_TIMEOUT)
	ctxWithToken, err := config.WithJWTToken(ctx, userID)
	if err != nil {
		log.L().Error("failed to attach JWT token to gRPC context", zap.Error(err))
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to attach JWT token"})
		cancel()
		return
	}
	defer cancel()
	var (
		fullContent string
		chunk       = &StreamMessageResponse{} //提前创建好空间，指针传入数据
	)
	// 调用stream对话
	err = global.GRPCClient.ChatStream(
		ctxWithToken,
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
						Content:  ch.Output,
						Final:    false,       // 这里只负责增量展示，最后的 final 另发一条
						NodeName: ch.NodeName, // 传递节点名称，用于前端判断是否是状态消息
					}
				} else {
					//如果是最终回复
					chunk = &StreamMessageResponse{ //响应的数据片
						Content:    ch.Output,
						TokenUsage: ch.Token, //这有最后一个才给token，因为这里是Langgraph节点传输
						Final:      true,     // 这里只负责增量展示，最后的 final 另发一条
						NodeName:   ch.NodeName,
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

// CancelConversation godoc
// @Summary     取消当前会话对应的大模型任务
// @Tags        Conversations
// @Security    BearerAuth
// @Produce     json
// @Param       id  path      string          true  "Conversation ID"
// @Success     200 {object}  CancelResponse
// @Failure     400 {object}  map[string]string
// @Failure     401 {object}  map[string]string
// @Failure     500 {object}  map[string]string
// @Router      /conversations/{id}/cancel [post]
// CancelConversation 取消当前会话对应的大模型任务
func CancelConversation(c *gin.Context) {
	userID, exists := c.Get("user_id")
	if !exists {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "Unauthorized"})
		return
	}

	convID := c.Param("id")
	if convID == "" {
		c.JSON(http.StatusBadRequest, gin.H{"error": "conversation id is required"})
		return
	}
	// 为 gRPC CancelTask 构造带超时和 JWT 的上下文
	ctx, cancel := context.WithTimeout(c.Request.Context(), CHAT_TIMEOUT)
	ctxWithToken, err := config.WithJWTToken(ctx, userID.(string)) // 上下文绑定对应的
	if err != nil {
		log.L().Error("failed to attach JWT token to gRPC context for cancel", zap.Error(err))
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to attach JWT token"})
		cancel()
		return
	}
	defer cancel()

	if err := global.GRPCClient.CancelTask(ctxWithToken, userID.(string), convID); err != nil {
		log.L().Error("CancelConversation failed to cancel task", zap.Error(err))
		c.JSON(http.StatusInternalServerError, &CancelResponse{
			Success: false,
			Message: "cancel task failed: " + err.Error(),
		})
		return
	}
	log.L().Debug("CancelConversation function successful to cancel task")
	c.JSON(http.StatusOK, &CancelResponse{
		Success: true,
		Message: "cancel requested",
	})
}

// 对话消息响应list
// ListMessagesResponse 获取会话消息列表的响应
type ListMessagesResponse struct {
	Messages []Message `json:"messages"`
}

// ListConversationMessages godoc
// @Summary     获取指定会话下的消息列表
// @Tags        Conversations
// @Security    BearerAuth
// @Produce     json
// @Param       id                path      string  true   "Conversation ID"
// @Param       limit             query     int     false  "最大返回条数，默认20，最大100"
// @Param       before_created_at query     string  false  "游标时间（RFC3339或RFC3339Nano）"
// @Param       before_id         query     string  false  "游标消息ID"
// @Success     200               {object}  ListMessagesResponse
// @Failure     400               {object}  map[string]string
// @Failure     401               {object}  map[string]string
// @Failure     404               {object}  map[string]string
// @Failure     500               {object}  map[string]string
// @Router      /conversations/{id}/messages [get]
// ListConversationMessages 获取指定会话下的所有消息（其结果按时间升序）
func ListConversationMessages(c *gin.Context) {
	userID, exists := c.Get("user_id")
	if !exists {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "Unauthorized"})
		return
	}

	convID := c.Param("id")
	if convID == "" {
		c.JSON(http.StatusBadRequest, gin.H{"error": "conversation id is required"})
		return
	}

	// 先校验会话是否存在且属于当前用户
	var conv models.Conversations //对话表
	if err := global.DB.Where("id = ? AND user_id = ?", convID, userID.(string)).First(&conv).Error; err != nil {
		if err == gorm.ErrRecordNotFound {
			c.JSON(http.StatusNotFound, gin.H{"error": "conversation not found"})
		} else {
			log.L().Error(" ListConversationMessages function failed to find conversation", zap.Error(err))
			c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to load conversation"})
		}
		return
	}

	limit := PAGE_SIZE
	if v := c.Query("limit"); v != "" {
		if n, err := strconv.Atoi(v); err == nil { //ASCII to Integer
			if n <= 0 {
				n = 1
			} else if n > 100 {
				n = 100
			}
			limit = n
		} else {
			log.L().Error("ListConversationMessages function failed to parse limit", zap.Error(err))
			c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to parse limit"})
			return
		}
	}
	// 搭建查询条件
	q := global.DB.Model(&models.Messages{}).
		Select("id", "role", "content", "created_at").
		Where("conversation_id = ?", convID)
	// 获取查询时间条件
	beforeCreatedAtStr := c.Query("before_created_at")
	beforeID := c.Query("before_id")
	if beforeCreatedAtStr != "" && beforeID != "" {
		beforeCreatedAt, err := time.Parse(time.RFC3339Nano, beforeCreatedAtStr)
		if err != nil {
			// 兼容 RFC3339
			beforeCreatedAt, err = time.Parse(time.RFC3339, beforeCreatedAtStr)
			if err != nil {
				c.JSON(http.StatusBadRequest, gin.H{"error": "invalid before_created_at"})
				return
			}
		}
		q = q.Where(
			"(created_at < ?) OR (created_at = ? AND id < ?)",
			beforeCreatedAt, beforeCreatedAt, beforeID,
		) //加入上述的时间限制条件
	} else if (beforeCreatedAtStr != "" && beforeID == "") || (beforeCreatedAtStr == "" && beforeID != "") {
		c.JSON(http.StatusBadRequest, gin.H{"error": "before_created_at and before_id must be provided together"})
		return
	}

	// 查询该会话下的所有消息-只查询需要的三个字段，默认升序顺序排序，从早到晚
	var messages []Message
	if err := q.Order("created_at DESC").Order("id DESC").Limit(limit).Find(&messages).Error; err != nil {
		log.L().Error(" ListConversationMessages function failed to query messages", zap.Error(err))
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to load messages"})
		return
	}
	for i, j := 0, len(messages)-1; i < j; i, j = i+1, j-1 {
		messages[i], messages[j] = messages[j], messages[i] //双向交换
	}
	// 这里MessageID是自增的
	c.JSON(http.StatusOK, &ListMessagesResponse{
		Messages: messages,
	})
}

type Conversation struct {
	ID               string     `json:"id"`
	ConversationName string     `json:"conversation_name"`
	LastMsgTime      *time.Time `json:"last_msg_time"`
}
type ListConversationsResponse struct {
	Conversations []Conversation `json:"conversations"`
}

// ListConversations 列出当前用户的会话列表 -这个就是全部的对话记录列表
// GET /api/v1/conversations
// ListConversations godoc
// @Summary     列出当前用户的会话列表
// @Tags        Conversations
// @Security    BearerAuth
// @Produce     json
// @Success     200  {object}  ListConversationsResponse
// @Failure     401  {object}  map[string]string
// @Failure     500  {object}  map[string]string
// @Router      /conversations [get]
func ListConversations(c *gin.Context) {
	userID, exists := c.Get("user_id")
	if !exists {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "Unauthorized"})
		return
	}
	// 这里查询用户的各个对话按照最后消息时间降序排序，没有消息的会话放在最后
	var convs []Conversation
	if err := global.DB.
		Select("ID", "conversation_name", "last_msg_time").
		Where("user_id = ?", userID.(string)).
		Order("last_msg_time DESC, updated_at DESC").
		Find(&convs).Error; err != nil {
		log.L().Error(" ListConversations function failed to query conversations", zap.Error(err))
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to load conversations"})
		return
	}
	c.JSON(http.StatusOK, &ListConversationsResponse{Conversations: convs})
}

type ModifiedConversationRequest struct {
	ConversationName string `json:"conversation_name"`
	PinToTop         bool   `json:"pin_to_top"`
}

// CreateConversation 对话的改名
// ModifiedConversation godoc
// @Summary     修改会话信息（重命名/置顶）
// @Tags        Conversations
// @Security    BearerAuth
// @Accept      json
// @Produce     json
// @Param       id    path      string                      true  "Conversation ID"
// @Param       data  body      ModifiedConversationRequest  true  "修改会话参数"
// @Success     200   {object}  map[string]string
// @Failure     400   {object}  map[string]string
// @Failure     401   {object}  map[string]string
// @Failure     500   {object}  map[string]string
// @Router      /conversations/{id} [patch]
func ModifiedConversation(c *gin.Context) {
	userID, exists := c.Get("user_id")
	if !exists {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "Unauthorized"})
		return
	}
	convID := c.Param("id")
	if convID == "" {
		c.JSON(http.StatusBadRequest, gin.H{"error": "conversation id is vaild, please check"})
		return
	}
	var req ModifiedConversationRequest
	if c.ShouldBindJSON(&req) != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "request body is vaild, please check"})
		return
	}
	now := time.Now() // 获取当前时间
	err := global.DB.Transaction(func(tx *gorm.DB) error {
		if req.ConversationName != "" {
			if err := tx.Model(&models.Conversations{}).Where("id = ? and user_id = ?", convID, userID.(string)).Update("conversation_name", req.ConversationName).Error; err != nil {
				return err
			}

		}
		if req.PinToTop {
			// 仅手动更新 last_msg_time，UpdatedAt 交给 GORM 自动维护
			if err := tx.Model(&models.Conversations{}).
				Where("id = ? and user_id = ?", convID, userID.(string)).
				Update("last_msg_time", now).Error; err != nil {
				return err
			}
		}
		return nil
	})

	if err != nil {
		log.L().Error("ModifiedConversation function failed to update", zap.Error(err))
		c.JSON(http.StatusInternalServerError, gin.H{
			"error": "failed to update conversation: " + err.Error(),
		})
		return
	}
	c.JSON(http.StatusOK, gin.H{"message": "conversation name updated successfully"})
}
