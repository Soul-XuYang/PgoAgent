package utils
import (
    "time"
    "sync"
)

// 令牌桶算法
type TokenBucket struct { 
    capacity int
    rate float64
    token int
    lock sync.Mutex
    lastTime time.Time
}

func InitTokenBucket(capacity int, rate float64) *TokenBucket {
    return &TokenBucket{capacity: capacity, rate: rate, token: capacity, lastTime: time.Now()}
}

func (tb *TokenBucket)TakeToken() bool{
    tb.lock.Lock()
    defer tb.lock.Unlock()
    now := time.Now()
    timeDelta := float64(now.Sub(tb.lastTime).Seconds())     // Sub() 是 time.Time 的方法，用于计算两个时间点之间的时间差
    // 时间有效才补上T令牌
    if timeDelta >= 1.0 {
        tb.token = min(tb.token+int(timeDelta* tb.rate), tb.capacity)  //截断小数点，必须是float64截断,当前的桶情况
    }
    tb.lastTime = now // 更新时间
    if tb.token > 0 {
        tb.token -= 1
        
        return true
    }
    // 令牌溢出-false
    return false
}