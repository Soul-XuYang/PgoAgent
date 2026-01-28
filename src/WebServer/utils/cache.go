package utils

//这里的缓存模块仅使用本地的内存模型来处理
import(
    "sync"
    "time"
    "container/list"
)

const (
    DefaultCleanInterval = 3  * time.Hour // 默认清理间隔为3天
    DefaultCacheSize     = 100000            // 默认缓存大小为100000
)

type LocalCache struct {
    lock          sync.RWMutex
    cacheMap      map[string]*list.Element // 使用map来存储键值对
    lruList       *list.List               // 使用双向链表实现LRU
    cleanInterval time.Duration            // 清理间隔
    size          int                      // 当前缓存大小
    stopChan      chan struct{}            // 用于停止清理协程
}

type CacheItem struct {
    Key   string
    Value interface{} // 存储的值
    Time  int64
}



func NewLocalCache(cleanInterval time.Duration) *LocalCache {
    if cleanInterval <= 0 {
        cleanInterval = DefaultCleanInterval
    }

    lc := &LocalCache{
        cacheMap:      make(map[string]*list.Element),
        lruList:       list.New(),
        cleanInterval: cleanInterval,
        stopChan:      make(chan struct{}),
    }

    // 启动定时清理协程 -副线程
    go lc.startCleaner() 

    return lc
}

// Set 设置缓存
func (lc *LocalCache) Set(key string, value interface{}) { // 这里key设置为username
    lc.lock.Lock()
    defer lc.lock.Unlock()
    // 如果key已存在，更新值并移到链表前端-哈希表
    if elem, exists := lc.cacheMap[key]; exists {
        item := elem.Value.(*CacheItem) // 其item是一个指针，指向的是CacheItem结构体
        item.Value = value
        item.Time = time.Now().Unix() // 更新其时间戳
        lc.lruList.MoveToFront(elem) //将元素移动到链表前端
        return
    }
    // 如果缓存已满，移除最久未使用的项
    if lc.size >= DefaultCacheSize {
        lc.evict()
    }else { //直接添加
        lc.size++
    }
    item := &CacheItem{ //放入表头
        Key:   key,
        Value: value,
        Time:  time.Now().Unix(),
    }
    elem := lc.lruList.PushFront(item) //加入到表头
    lc.cacheMap[key] = elem
}

// Get 获取缓存
func (lc *LocalCache) Get(key string) (interface{}, bool) {
    lc.lock.Lock()
    defer lc.lock.Unlock()

    if elem, exists := lc.cacheMap[key]; exists {
        lc.lruList.MoveToFront(elem) //将该元素移动到链表前端
        return elem.Value.(*CacheItem).Value, true
    }
    return nil, false
}


func (lc *LocalCache) evict() { //移除最久未使用的项
    lc.lock.Lock()
    defer lc.lock.Unlock()
    elem := lc.lruList.Back()
    if elem != nil {
        lc.Delete(elem.Value.(*CacheItem).Key) //移除对应的元素
    }
}

// Delete 移除指定项
func (lc *LocalCache) Delete(key string) { //双向链表元素指针
    lc.lock.Lock()
    defer lc.lock.Unlock()
    if element, exists := lc.cacheMap[key]; exists {
        lc.lruList.Remove(element)
        delete(lc.cacheMap, key)
        lc.size--
    }
    // 不存在则不做任何操作
}

// startCleaner 启动定时清理器
func (lc *LocalCache) startCleaner() {
    ticker := time.NewTicker(lc.cleanInterval) //创建一个定时器
    defer ticker.Stop() //上下文管理
    for {
        select {
        case <-ticker.C: //通道
            lc.clean()
        case <-lc.stopChan: //通道结束
            return
        }
    }
}

// clean 清理过期的缓存项
func (lc *LocalCache) clean() {
    lc.lock.Lock()
    defer lc.lock.Unlock()

    now := time.Now().Unix()
    for elem := lc.lruList.Back(); elem != nil; {
        item := elem.Value.(*CacheItem)
        // 如果项目未过期，停止清理
        if item.Time > now-int64(lc.cleanInterval.Seconds()) {
            break
        }
        prev := elem.Prev()
        lc.Delete(elem.Value.(*CacheItem).Key)
        elem = prev
    }
}

//提供关闭缓存选项-Close 关闭通道，停止清理协程
func (lc *LocalCache) Close() {
    close(lc.stopChan)
}