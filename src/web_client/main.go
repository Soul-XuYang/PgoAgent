package main

import (
	"context"
	"fmt"
	"io"
	"time"

	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
	
	agent_grpc "Pgoagent/agent_grpc" // 根据你的实际包路径调整
	"Pgoagent/log"
	"go.uber.org/zap"
)

func main() {
	// 初始化日志
	if err := log.Init(false); err != nil {
		panic(err)
	}
	defer log.Sync()

	// 连接 gRPC 服务器
	conn, err := grpc.NewClient(
		"localhost:50051",
		grpc.WithTransportCredentials(insecure.NewCredentials()),
	)
	if err != nil {
		log.L().Fatal("连接失败", zap.Error(err))
	}
	defer conn.Close()

	client := agent_grpc.NewAgentServiceClient(conn)

	// 示例1: 非流式对话
	testChat(client)

	// 示例2: 流式对话
	testChatStream(client)

	// 示例3: 获取对话历史
	testGetHistory(client)
}

func testChat(client agent_grpc.AgentServiceClient) {
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	req := &agent_grpc.ChatRequest{
		UserInput: "你好，请介绍一下你自己",
		UserConfig: &agent_grpc.UserConfig{
			ThreadId:      "thread_001",
			UserId:        "user_001",
			ChatMode:      "normal",
			RecursionLimit: 50,
		},
	}

	resp, err := client.Chat(ctx, req)
	if err != nil {
		log.L().Error("Chat 调用失败", zap.Error(err))
		return
	}

	if resp.Success {
		fmt.Printf("回复: %s\n", resp.Reply)
		fmt.Printf("Token 使用量: %d\n", resp.TokenUsage)
	} else {
		fmt.Printf("错误: %s\n", resp.ErrorMessage)
	}
}

func testChatStream(client agent_grpc.AgentServiceClient) {
	ctx, cancel := context.WithTimeout(context.Background(), 60*time.Second)
	defer cancel()

	req := &agent_grpc.ChatRequest{
		UserInput: "请详细介绍一下 LangGraph",
		UserConfig: &agent_grpc.UserConfig{
			ThreadId:      "thread_001",
			UserId:        "user_001",
			ChatMode:      "stream",
			RecursionLimit: 50,
		},
	}

	stream, err := client.ChatStream(ctx, req)
	if err != nil {
		log.L().Error("ChatStream 调用失败", zap.Error(err))
		return
	}

	fmt.Println("开始接收流式响应:")
	for {
		chunk, err := stream.Recv()
		if err == io.EOF {
			break
		}
		if err != nil {
			log.L().Error("接收流式数据失败", zap.Error(err))
			break
		}

		if chunk.FinalResponse {
			fmt.Printf("\n[最终回复] %s\n", chunk.Output)
			fmt.Printf("[Token] %d\n", chunk.Token)
		} else {
			fmt.Printf("\r[状态] %s", chunk.Output)
		}
	}
	fmt.Println("\n流式响应结束")
}

func testGetHistory(client agent_grpc.AgentServiceClient) {
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	req := &agent_grpc.HistoryRequest{
		UserConfig: &agent_grpc.UserConfig{
			ThreadId:      "thread_001",
			UserId:        "user_001",
			ChatMode:      "normal",
			RecursionLimit: 50,
		},
	}

	resp, err := client.GetConversationHistory(ctx, req)
	if err != nil {
		log.L().Error("GetConversationHistory 调用失败", zap.Error(err))
		return
	}

	fmt.Printf("累计 Token 使用量: %d\n", resp.CumulativeUsage)
	fmt.Printf("摘要: %s\n", resp.Summary)
	fmt.Printf("对话历史 (%d 条):\n", len(resp.LatestConversation))
	for i, pair := range resp.LatestConversation {
		fmt.Printf("  [%d] %s: %s\n", i+1, pair.Role, pair.Content)
	}
}