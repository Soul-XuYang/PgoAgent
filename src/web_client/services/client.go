package services

import (
	agent_grpc "PgoAgent/agent_grpc" //对应的proto文件
	"context"
	"fmt"
	"net"
	"path/filepath"
	"runtime"
	"strconv"
	"sync"
	"time"

	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials"
	"google.golang.org/grpc/encoding/gzip"
)

// 构建对应的grpc客户端包代码

var DefaultTimeout = 30 * time.Second // 默认超时时间
const RecursionLimit = 50             // 递归限制次数
// 全局结构体和方法
type Client struct {
	conn     *grpc.ClientConn
	client   agent_grpc.AgentServiceClient // grpc客户端
	mu       sync.RWMutex                  // 互斥做
	isClosed bool                          // 是否关闭
}

// 获取对应的证书路径
func getCertPath() string {
	_, filename, _, _ := runtime.Caller(0)
	dir := filepath.Dir(filename)
	return filepath.Join(dir, "..", "..", "..", "certs", "server.crt") //对应路径下的证书文件含公钥信息
}

// 创建客户端
func NewClient(host string, port int, sendSize int, receiveSize int) (*Client, error) {
	address := net.JoinHostPort(host, strconv.Itoa(port)) // 构建网络地址

	// 客户端默认使用 TLS，确保安全连接
	var creds credentials.TransportCredentials
	var err error
	certPath := getCertPath()
	// 校验名称与服务端匹配
	creds, err = credentials.NewClientTLSFromFile(certPath, "localhost")
	if err != nil {
		return nil, fmt.Errorf("failed to load TLS certificate from %s: %w", certPath, err)
	}
	
	// 客户端包含对应的证书
	// 注意：grpc.NewClient 是异步的，不会阻塞。连接会在第一次 RPC 调用时建立
	conn, err := grpc.NewClient(
		address,
		grpc.WithTransportCredentials(creds),
		grpc.WithDefaultCallOptions(grpc.UseCompressor(gzip.Name)),                  // 使用gzip压缩
		grpc.WithDefaultCallOptions(grpc.MaxCallSendMsgSize(sendSize*1024*1024)),    // 客户端发送上限
		grpc.WithDefaultCallOptions(grpc.MaxCallRecvMsgSize(receiveSize*1024*1024)), // 客户端接收上限
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
// 注意：默认使用 TLS，如果 opts 中包含 TransportCredentials 选项，将使用用户指定的选项
func NewClientWithOptions(host string, port int, opts ...grpc.DialOption) (*Client, error) {
	address := net.JoinHostPort(host, strconv.Itoa(port))
	
	// 默认使用 TLS（如果用户没有在 opts 中指定 TransportCredentials，gRPC 会使用第一个）
	// 使用 "localhost" 作为服务器名称，与证书的 CN 匹配
	creds, err := credentials.NewClientTLSFromFile(getCertPath(), "localhost")
	if err != nil {
		return nil, fmt.Errorf("failed to load TLS certificate: %w", err)
	}
	// 将 TLS 选项放在最前面，如果用户提供了 TransportCredentials，应该放在 opts 中覆盖
	defaultOpts := []grpc.DialOption{grpc.WithTransportCredentials(creds)}
	opts = append(defaultOpts, opts...)
	
	conn, err := grpc.NewClient(
		address,
		opts...,
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
