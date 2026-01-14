package grpc_client
// proto文件对应的各种调用
import (
    "context"
    "fmt"
    "io"
    "PgoAgent/log"
    "go.uber.org/zap"
    "google.golang.org/protobuf/types/known/emptypb"
	"google.golang.org/grpc/metadata"
    agent_grpc "PgoAgent/agent_grpc" //对应的proto文件
)
// 这里请求都用现有的结构体格式

// Chat 非流式对话
func (c *Client) Chat(ctx context.Context, userInput string, userID, threadID string, opts ...ChatOption) (*ChatResponse, error) {
	if !c.IsConnected() {
		return nil, fmt.Errorf("gRPC client is closed")
	}

	config := &ChatConfig{
		ChatMode:      "normal",
		RecursionLimit: RecursionLimit,
	}
	for _, opt := range opts {
		opt(config)
	}
    token, err := GenerateJWTToken(userID) // 使用 userID 作为 userName
	if err != nil {
		log.L().Error("Failed to generate JWT token", zap.Error(err))
		return nil, fmt.Errorf("failed to generate JWT token: %w", err)
	}
	ctx = metadata.AppendToOutgoingContext(ctx, "authorization", "Bearer "+token)

	req := &agent_grpc.ChatRequest{
		UserInput: userInput,
		UserConfig: &agent_grpc.UserConfig{
			ThreadId:       threadID,
			UserId:         userID,
			ChatMode:       config.ChatMode,
			RecursionLimit: config.RecursionLimit,
		},
	}

	resp, err := c.client.Chat(ctx, req)
	if err != nil {
		log.L().Error("Chat RPC failed", zap.Error(err))
		return nil, fmt.Errorf("chat RPC failed: %w", err)
	}

	if !resp.Success {
		return nil, fmt.Errorf("chat failed: %s", resp.ErrorMessage)
	}
	return &ChatResponse{
		Reply:      resp.Reply,
		TokenUsage: resp.TokenUsage,
	}, nil
}

// ChatStream 流式对话
func (c *Client) ChatStream(ctx context.Context, userInput string, userID, threadID string, handler StreamHandler, opts ...ChatOption) error {
	if !c.IsConnected() {
		return fmt.Errorf("gRPC client is closed")
	}
    
	config := &ChatConfig{
		ChatMode:      "stream",
		RecursionLimit: RecursionLimit,
	}
	for _, opt := range opts {
		opt(config)
	}
    token, err := GenerateJWTToken(userID) // 使用 userID 作为 userName
	if err != nil {
		log.L().Error("Failed to generate JWT token", zap.Error(err))
		return fmt.Errorf("failed to generate JWT token: %w", err)
	}
	ctx = metadata.AppendToOutgoingContext(ctx, "authorization", "Bearer "+token) //追加JWTtoken
	req := &agent_grpc.ChatRequest{
		UserInput: userInput,
		UserConfig: &agent_grpc.UserConfig{
			ThreadId:       threadID,
			UserId:         userID,
			ChatMode:       "stream",
			RecursionLimit: config.RecursionLimit,
		},
	}

	stream, err := c.client.ChatStream(ctx, req)
	if err != nil {
		log.L().Error("ChatStream RPC failed", zap.Error(err))
		return fmt.Errorf("chat stream RPC failed: %w", err)
	}

	for {
		chunk, err := stream.Recv()
		if err == io.EOF {
			break
		}
		if err != nil {
			log.L().Error("Failed to receive stream chunk", zap.Error(err))
			return fmt.Errorf("failed to receive stream chunk: %w", err)
		}

		// 调用处理函数
		if handler != nil {
			if err := handler(&StreamChunk{
				Output:        chunk.Output,
				FinalResponse: chunk.FinalResponse,
				Token:         chunk.Token,
				NodeName:      chunk.NodeName,
			}); err != nil {
				return err
			}
		}
	}

	return nil
}

// GetConversationHistory 获取对话历史
func (c *Client) GetConversationHistory(ctx context.Context, userID , threadID string) (*HistoryResponse, error) {
	if !c.IsConnected() {
		return nil, fmt.Errorf("gRPC client is closed")
	}
    
    token, err := GenerateJWTToken(userID) // 使用 userID 作为 userName
	if err != nil {
		log.L().Error("Failed to generate JWT token", zap.Error(err))
		return nil,fmt.Errorf("failed to generate JWT token: %w", err)
	}
	ctx = metadata.AppendToOutgoingContext(ctx, "authorization", "Bearer "+token) //追加JWTtoken

	req := &agent_grpc.HistoryRequest{
		UserConfig: &agent_grpc.UserConfig{
			ThreadId:       threadID,
			UserId:         userID,
			ChatMode:       "normal",
			RecursionLimit: RecursionLimit,
		},
	}
    // 调用 GetConversationHistory 方法 进行封装
	resp, err := c.client.GetConversationHistory(ctx, req)
	if err != nil {
		log.L().Error("GetConversationHistory RPC failed", zap.Error(err))
		return nil, fmt.Errorf("get history RPC failed: %w", err)
	}
    
	conversations := make([]ConversationPair, len(resp.LatestConversation))
	for i, pair := range resp.LatestConversation {
		conversations[i] = ConversationPair{
			Role:      pair.Role,
			Content:   pair.Content,
			Timestamp: pair.Timestamp,
		}
	}

	return &HistoryResponse{
		Conversations:    conversations,
		CumulativeUsage:  resp.CumulativeUsage,
		Summary:          resp.Summary,
	}, nil
}

// CancelTask 取消任务- 需要针对对应用户和对应的线程进行取消
func (c *Client) CancelTask(ctx context.Context, userID, threadID string) error {
	if !c.IsConnected() {
		return fmt.Errorf("gRPC client is closed")
	}
    token, err := GenerateJWTToken(userID) // 使用 userID 作为 userName
	if err != nil {
		log.L().Error("Failed to generate JWT token", zap.Error(err))
		return fmt.Errorf("failed to generate JWT token: %w", err)
	}
	ctx = metadata.AppendToOutgoingContext(ctx, "authorization", "Bearer "+token) //追加JWTtoken
	req := &agent_grpc.CancelRequest{
		UserId:   userID,
		ThreadId: threadID,
	}

	resp, err := c.client.CancelTask(ctx, req)
	if err != nil {
		log.L().Error("CancelTask RPC failed", zap.Error(err))
		return fmt.Errorf("cancel task RPC failed: %w", err)
	}

	if !resp.Success {
		return fmt.Errorf("cancel task failed: %s", resp.Message)
	}

	return nil
}

// GetServerInfo 获取服务器信息,无请求信息无需调用对应的请求结构体- -这里无需jwt验证，可以直接跳过
func (c *Client) GetServerInfo(ctx context.Context) (*ServerInfo, error) {
	if !c.IsConnected() {
		return nil, fmt.Errorf("gRPC client is closed")
	}
    
	resp, err := c.client.GetServerInfo(ctx, &emptypb.Empty{})
	if err != nil {
		log.L().Error("GetServerInfo RPC failed", zap.Error(err))
		return nil, fmt.Errorf("get server info RPC failed: %w", err)
	}

	return &ServerInfo{
		Version:  resp.Version,
		StartTime: resp.StartTime,
		RunTime:  resp.RunTime,
	}, nil
}

