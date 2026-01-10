// src/web_client/grpc_client/types.go
package grpc_client

// ChatResponse 对话响应
type ChatResponse struct {
	Reply      string
	TokenUsage int32
}

// StreamChunk 流式输出块
type StreamChunk struct {
	Output        string
	FinalResponse bool
	Token         int32
	NodeName      string
}

// StreamHandler 流式处理函数
type StreamHandler func(chunk *StreamChunk) error // 流式响应

// ConversationPair 角色对话内容列表
type ConversationPair struct {
	Role      string
	Content   string
	Timestamp int64
}

// HistoryResponse 历史记录响应
type HistoryResponse struct {
	Conversations   []ConversationPair
	CumulativeUsage int32
	Summary         string
}

// ServerInfo 服务器信息
type ServerInfo struct {
	Version string
    StartTime string
	RunTime string
}

// Cancel取消响应
type CancelRequest struct {
    Success bool
    ErrorMsg string
}

// ===== 以下为客户端的本身的输入配置 ======

// ChatConfig 对话配置
type ChatConfig struct {
	ChatMode      string
	RecursionLimit int32
}

// ChatOption 对话选项
type ChatOption func(*ChatConfig)

// WithChatMode 设置聊天模式
func SetChatMode(mode string) ChatOption {
	return func(c *ChatConfig) {
		c.ChatMode = mode
	}
}
// WithRecursionLimit 设置递归限制
func SetRecursionLimit(limit int32) ChatOption {
	return func(c *ChatConfig) {
		c.RecursionLimit = limit
	}
}