package grpc_client

import (
	"fmt"
	"sync"
	"time"
	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
	agent_grpc "PgoAgent/agent_grpc" //对应的proto文件
	"strconv"
	"net"
	"context"
)

// 构建对应的grpc客户端包代码

var DefaultTimeout = 30 * time.Second // 默认超时时间
const RecursionLimit = 50 // 递归限制次数
// 全局结构体和方法
type Client struct { 
	conn *grpc.ClientConn
	client agent_grpc.AgentServiceClient // grpc客户端
	mu sync.RWMutex// 互斥做
	isClosed bool // 是否关闭
}

// 创建客户端
func NewClient(host string, port int) (*Client, error) {
	address := net.JoinHostPort(host, strconv.Itoa(port))
	
	if host == "localhost" {
		address = net.JoinHostPort(host, strconv.Itoa(port))
	}
	
	conn, err := grpc.NewClient(
		address,
		grpc.WithTransportCredentials(insecure.NewCredentials()),
	)
	if err != nil {
		return nil, fmt.Errorf("failed to create gRPC client: %w", err)
	}
	return &Client{
		conn:     conn,
		client:   agent_grpc.NewAgentServiceClient(conn),
		isClosed: false,
	}, nil
}



// NewClientWithOptions 使用自定义选项创建客户端
func NewClientWithOptions(host string,port int, opts ...grpc.DialOption) (*Client, error) {
	address := net.JoinHostPort(host, strconv.Itoa(port))
	opts = append(opts,grpc.WithTransportCredentials(insecure.NewCredentials()))
    conn, err := grpc.NewClient(
		address,
		opts...,
	)
	if err != nil {
		return nil, fmt.Errorf("failed to create gRPC client: %w", err)
	}
	return &Client{
		conn:   conn,
		client: agent_grpc.NewAgentServiceClient(conn),
		isClosed: false,  
	}, nil
}

// Close 关闭连接
func (c *Client) Close() error {
	c.mu.Lock()
	defer c.mu.Unlock()
	
	if c.isClosed {
		return nil
	}
	
	c.isClosed = true
	if c.conn != nil {
		return c.conn.Close()
	}
	return nil
}

// IsConnected 读取并检查连接是否有效
func (c *Client) IsConnected() bool {
	c.mu.RLock()
	defer c.mu.RUnlock()
	return !c.isClosed && c.conn != nil
}

// 创建默认的上下文使用
func (c *Client) WithTimeout(timeout time.Duration) (context.Context, context.CancelFunc) {
	if timeout <= 0 { 
        fmt.Printf("Invalid timeout parameter, Use default timeout: {%v}\n", DefaultTimeout)
		return context.WithTimeout(context.Background(), DefaultTimeout)
	}
	return context.WithTimeout(context.Background(), timeout)
}