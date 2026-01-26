package utils

import (
    "testing"
    "time"
    "sync"
    "fmt"
)

// TestTokenBucket_BasicFunction 测试基本功能
func TestTokenBucket_BasicFunction(t *testing.T) {
    // 创建容量为10，速率为2个/秒的令牌桶
    tb := InitTokenBucket(10, 2)
    
    // 初始取10个令牌
    fmt.Println("Initilized token:",tb.token)
    for i := 0; i < 10; i++ {
        if !tb.TakeToken() {
            t.Errorf("Expected to get token %d, but failed", i)
        }
    }
    
    // 第11个令牌应该获取失败
    if tb.TakeToken() {
        t.Error("Expected to fail getting token after bucket is empty, but succeeded")
    }
}

// TestTokenBucket_RateLimit 测试速率限制
func TestTokenBucket_RateLimit(t *testing.T) {
    tb := InitTokenBucket(5, 2) // 容量5，速率2个/秒
    fmt.Println("Initilized token:",tb.token)
    // 先用完所有令牌
    for i := 0; i < 5; i++ {
        tb.TakeToken()
    }
    
    // 等待1秒，应该可以获取2个令牌
    time.Sleep(1 * time.Second)
    if !tb.TakeToken() {
        t.Error("Expected to get token after 1 second, but failed")
    }
    if !tb.TakeToken() {
        t.Error("Expected to get second token after 1 second, but failed")
    }
    if !tb.TakeToken() {
        fmt.Println("It's ok, tokenbucket is empty: ",tb.token)
    }
}

// TestTokenBucket_ConcurrentAccess 测试并发安全性
func TestTokenBucket_ConcurrentAccess(t *testing.T) {
    tb := InitTokenBucket(100000, 10) 
    var wg sync.WaitGroup // 创建等待组
    var successCount int64
    var mu sync.Mutex

    fmt.Println("Initilized token:",tb.token)
    for i := 0; i < 1000; i++ {
        wg.Add(1)
        go func() {
            defer wg.Done()
            for j := 0; j < 100; j++ {
                if tb.TakeToken() {
                    mu.Lock()
                    successCount++
                    mu.Unlock()
                }else{
                t.Error("Expected to get token, but failed")
            }
                time.Sleep(10 * time.Millisecond) // 模拟处理时间
            }

        }()
    }
    wg.Wait()    
    fmt.Printf("Successfully got %d tokens in concurrent test\n", successCount)
    fmt.Printf("Remaining tokens after test are empty: %d\n", tb.token)
}

// TestTokenBucket_LongRunning 测试长时间运行的稳定性
func TestTokenBucket_LongRunning(t *testing.T) {
    tb := InitTokenBucket(10, 5) // 容量10，速率5个/秒
    
    startTime := time.Now()
    var successCount int
    
    // 运行3秒
    for time.Since(startTime) < 3*time.Second {
        if tb.TakeToken() {
            successCount++
        }
        time.Sleep(50 * time.Millisecond)
    }

    expectedTokens := 10 + int(3*5) // 初始10 + 3秒*5个/秒
    
    // 允许一定误差（由于时间精度和执行延迟）
    if successCount < expectedTokens-2 || successCount > expectedTokens {
        t.Errorf("Expected tokens around %d, but got %d", expectedTokens, successCount)
    }
    
    fmt.Printf("Got %d tokens in 3 seconds (expected around %d)\n", successCount, expectedTokens)
}

// BenchmarkTokenBucket 性能测试
func BenchmarkTokenBucket(b *testing.B) {
    tb := InitTokenBucket(1000, 1000)
    b.ResetTimer()
    b.RunParallel(func(pb *testing.PB) {
        for pb.Next() {
            tb.TakeToken()
        }
    })
}
