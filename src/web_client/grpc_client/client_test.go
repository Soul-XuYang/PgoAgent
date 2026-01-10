// src/web_client/grpc_client/client_test.go
package grpc_client

import (
	"context"
	"fmt"
	"testing" //测试包
	"PgoAgent/config"
	"PgoAgent/log"
)

// TestClient_Connection 测试客户端连接
func TestClient_Connection(t *testing.T) {
	// 初始化日志
	if err := log.Init(false); err != nil {
		t.Fatalf("Failed to init log: %v", err)
	}
	defer log.Sync()

	// 加载配置
	cfg, err := config.LoadConfig(config.ConfigPath)
	if err != nil {
		t.Fatalf("Failed to load config: %v", err)
	}

	// 创建客户端
	client, err := NewClient(cfg.GRPC.Server.Host, cfg.GRPC.Server.Port)
	if err != nil {
		t.Fatalf("Failed to create client: %v", err)
	}
	defer client.Close()

	// 测试连接状态
	if !client.IsConnected() {
		t.Error("Client should be connected")
	}

	// 测试关闭连接
	if err := client.Close(); err != nil {
		t.Errorf("Failed to close client: %v", err)
	}

	if client.IsConnected() {
		t.Error("Client should be disconnected after Close()")
	}
}

// TestClient_Chat 测试非流式对话
func TestClient_Chat(t *testing.T) {
	if testing.Short() {
		t.Skip("Skipping integration test in short mode")
	}

	// 初始化
	if err := log.Init(false); err != nil {
		t.Fatalf("Failed to init log: %v", err)
	}
	defer log.Sync()

	cfg, err := config.LoadConfig(config.ConfigPath)
	if err != nil {
		t.Fatalf("Failed to load config: %v", err)
	}

	client, err := NewClient(cfg.GRPC.Server.Host, cfg.GRPC.Server.Port)
	if err != nil {
		t.Fatalf("Failed to create client: %v", err)
	}
	defer client.Close()

	ctx, cancel := client.WithTimeout(DefaultTimeout)
	defer cancel()

	// 测试基本对话
	resp, err := client.Chat(ctx, "你好", "test_user_001", "test_thread_001")
	if err != nil {
		t.Fatalf("Chat failed: %v", err)
	}

	if resp.Reply == "" {
		t.Error("Expected non-empty reply")
	}

	fmt.Printf("Reply: %s\n", resp.Reply)
	fmt.Printf("Token Usage: %d\n", resp.TokenUsage)

	// 测试带选项的对话
	resp2, err := client.Chat(ctx, "user_003", "test_user_001", "002",
		SetChatMode("normal"),
		SetRecursionLimit(30),
	)
	if err != nil {
		t.Fatalf("Chat with options failed: %v", err)
	}

	if resp2 == nil {
		t.Error("Expected non-nil response")
	}
}

// TestClient_ChatStream 测试流式对话
func TestClient_ChatStream(t *testing.T) {
	if testing.Short() {
		t.Skip("Skipping integration test in short mode")
	}

	if err := log.Init(false); err != nil {
		t.Fatalf("Failed to init log: %v", err)
	}
	defer log.Sync()

	cfg, err := config.LoadConfig(config.ConfigPath)
	if err != nil {
		t.Fatalf("Failed to load config: %v", err)
	}

	client, err := NewClient(cfg.GRPC.Server.Host, cfg.GRPC.Server.Port)
	if err != nil {
		t.Fatalf("Failed to create client: %v", err)
	}
	defer client.Close()

	ctx, cancel := client.WithTimeout(DefaultTimeout)
	defer cancel()

	var chunks []*StreamChunk
	var finalChunk *StreamChunk

	err = client.ChatStream(ctx, "你好，请介绍一下你自己", "user_003", "002",
		func(chunk *StreamChunk) error {
			chunks = append(chunks, chunk)
			if chunk.FinalResponse {
				finalChunk = chunk
			} else {
				fmt.Printf("\r[状态] %s", chunk.Output)
			}
			return nil
		},
		SetRecursionLimit(50),
	)

	if err != nil {
		t.Fatalf("ChatStream failed: %v", err)
	}

	if finalChunk == nil {
		t.Error("Expected final chunk")
	} else {
		fmt.Printf("\n[最终回复] %s\n", finalChunk.Output)
		fmt.Printf("[Token] %d\n", finalChunk.Token)
	}

	if len(chunks) == 0 {
		t.Error("Expected at least one chunk")
	}
}

// TestClient_GetConversationHistory 测试获取对话历史
func TestClient_GetConversationHistory(t *testing.T) {
	if testing.Short() {
		t.Skip("Skipping integration test in short mode")
	}

	if err := log.Init(false); err != nil {
		t.Fatalf("Failed to init log: %v", err)
	}
	defer log.Sync()

	cfg, err := config.LoadConfig(config.ConfigPath)
	if err != nil {
		t.Fatalf("Failed to load config: %v", err)
	}

	client, err := NewClient(cfg.GRPC.Server.Host, cfg.GRPC.Server.Port)
	if err != nil {
		t.Fatalf("Failed to create client: %v", err)
	}
	defer client.Close()

	ctx, cancel := client.WithTimeout(DefaultTimeout)
	defer cancel()

	// 获取历史
	history, err := client.GetConversationHistory(ctx, "user_003", "002")
	if err != nil {
		t.Fatalf("GetConversationHistory failed: %v", err)
	}

	fmt.Printf("累计 Token: %d\n", history.CumulativeUsage)
	fmt.Printf("摘要: %s\n", history.Summary)
	fmt.Printf("最近的对话数量数量: %d\n", len(history.Conversations))
    // 切片类型
	for i, pair := range history.Conversations {
		fmt.Printf("  [%d] %s: %s\n", i+1, pair.Role, pair.Content)
	}
}

// // TestClient_CancelTask 测试取消任务
// func TestClient_CancelTask(t *testing.T) {
// 	if testing.Short() {
// 		t.Skip("Skipping integration test in short mode")
// 	}

// 	if err := log.Init(false); err != nil {
// 		t.Fatalf("Failed to init log: %v", err)
// 	}
// 	defer log.Sync()

// 	cfg, err := config.LoadConfig(config.ConfigPath)
// 	if err != nil {
// 		t.Fatalf("Failed to load config: %v", err)
// 	}

// 	client, err := NewClient(cfg.GRPC.Client.Host, cfg.GRPC.Client.Port)
// 	if err != nil {
// 		t.Fatalf("Failed to create client: %v", err)
// 	}
// 	defer client.Close()

// 	ctx, cancel := client.WithTimeout(DefaultTimeout)
// 	defer cancel()

// 	// 注意：这个测试需要在实际运行任务时才能测试取消功能
// 	// 这里只是测试接口调用
// 	err = client.CancelTask(ctx, "test_user_004", "test_thread_004")
// 	if err != nil {
// 		// 如果任务不存在，这是预期的错误
// 		fmt.Printf("CancelTask (expected if no running task): %v\n", err)
// 	}
// }

// TestClient_GetServerInfo 测试获取服务器信息
func TestClient_GetServerInfo(t *testing.T) {
    fmt.Println("Test: start to get ServerInfo")
	if testing.Short() {
		t.Skip("Skipping integration test in short mode")
	}

	if err := log.Init(false); err != nil {
		t.Fatalf("Failed to init log: %v", err)
	}
	defer log.Sync()

	cfg, err := config.LoadConfig(config.ConfigPath)
	if err != nil {
		t.Fatalf("Failed to load config: %v", err)
	}
    fmt.Println("client has created successfully: ",cfg.GRPC.Server.Host, cfg.GRPC.Server.Port)
	client, err := NewClient(cfg.GRPC.Server.Host, cfg.GRPC.Server.Port)
	if err != nil {
		t.Fatalf("Failed to create client connection: %v", err)
	}
    fmt.Println("client has created successfully")
	defer client.Close()

	ctx, cancel := client.WithTimeout(DefaultTimeout)
	defer cancel()

	info, err := client.GetServerInfo(ctx)
	if err != nil {
		t.Fatalf("GetServerInfo failed: %v", err)
	}

	if info.Version == "" {
		t.Error("Expected non-empty version")
	}

	fmt.Printf("服务器版本: %s\n", info.Version)
    fmt.Printf("服务器启动时间： %s\n",info.StartTime)
	fmt.Printf("运行时间: %s\n", info.RunTime)
}

// Benchmark对于Client_Chat 性能基准测试
func BenchmarkClient_Chat(b *testing.B) {
	if err := log.Init(true); err != nil {
		b.Fatalf("Failed to init log: %v", err)
	}

	cfg, err := config.LoadConfig(config.ConfigPath)
	if err != nil {
		b.Fatalf("Failed to load config: %v", err)
	}

	client, err := NewClient(cfg.GRPC.Server.Host, cfg.GRPC.Server.Port)
	if err != nil {
		b.Fatalf("Failed to create client: %v", err)
	}
	defer client.Close()

	ctx := context.Background() //基础的空上下文
    // 重置计时器以排除初始化时间
	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		_, err := client.Chat(ctx, "benchmark test", "bench_user", fmt.Sprintf("bench_thread_%d", i))
		if err != nil {
			b.Errorf("Chat failed: %v", err)
		}
	}
}