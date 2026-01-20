import grpc
import asyncio
import time
from agent.config import logger
from .abort import _abort_like_handler # 获取对应的阻拦函数
from typing import Optional


NS = 1_000_000_000 # 纳秒
# 这里构建一个令牌桶
class TokenBucket:
    """整数令牌桶
    按照容量和每秒的速率计算
    """
    def __init__(self, rate_per_sec: float, capacity: int):
        if rate_per_sec <= 0:
            raise ValueError("rate_per_sec must be > 0")
        if capacity <= 0:
            raise ValueError("capacity must be > 0")
        self.capacity = int(capacity)
        self.tokens = int(capacity) # 初始化是全满的令牌
        self.ns_per_token = max(1, int(NS / float(rate_per_sec))) # 每个令牌的纳秒数,NS是1秒的纳秒数
        self.last_ns = time.monotonic_ns()       # self.last_ns = time.monotonic_ns()当前的纳秒数

    def try_take_token(self, cost: int = 1) -> bool:
        now = time.monotonic_ns()
        elapsed = now - self.last_ns
        add = elapsed // self.ns_per_token
        if add >= 1:
            new_tokens = self.tokens + add
            self.tokens = new_tokens if new_tokens < self.capacity else self.capacity
            self.last_ns = now

        if self.tokens >= cost:
            self.tokens -= cost
            return True
        return False


class GlobalRateLimitInterceptor(grpc.aio.ServerInterceptor):
    """
    全局限流拦截器（QPS，按秒）
    时间复杂度: O(1) - 单次检查是常数时间
    """
    def __init__(
        self,
        global_rate_per_sec: float = 100,
        global_burst: int = 200,
        skip_methods: Optional[list] = None,
    ):
        self.skip_methods = set(skip_methods or [])
        self._bucket = TokenBucket(global_rate_per_sec, global_burst)
        self._lock = asyncio.Lock()

    async def intercept_service(self, continuation, handler_call_details):
        method_name = handler_call_details.method.split("/")[-1]
        if method_name in self.skip_methods:
            return await continuation(handler_call_details)

        # 先检查限流，再获取 handler
        async with self._lock:
            allowed = self._bucket.try_take_token(1)

        if not allowed:
            logger.warning(f"GlobalRateLimit: triggered, limit: {self._bucket.capacity}, method={method_name}")
            # 需要先获取 handler 才能 abort
            handler = await continuation(handler_call_details)
            return _abort_like_handler(
                handler,
                grpc.StatusCode.RESOURCE_EXHAUSTED,
                "请求过于频繁，请稍后再试（全局限流）"
            )
        
        return await continuation(handler_call_details)

class UserRateLimitInterceptor(grpc.aio.ServerInterceptor):
    """
    用户限流拦截器（按分钟 RPM）
    需要从 metadata 里拿 user_id。
    """
    def __init__(
        self,
        user_rate_per_minute: float = 60,    # RPM
        user_burst: int = 120,    # 默认=RPM
        user_id_metadata_key: str = "user_id",
        skip_methods=None,
        shards: int = 64, # 默认分片数
        bucket_ttl_sec: int = 30 * 60,       # 30min 未访问就清理
        cleanup_interval_sec: int = 60 # 防止过多的令牌桶数量
    ):
        # 桶参数算法
        self.skip_methods = set(skip_methods or [])
        self.user_id_metadata_key = user_id_metadata_key
        rate_per_sec = float(user_rate_per_minute) / 60.0
        capacity = user_burst
        self._rate_per_sec = rate_per_sec
        self._capacity = capacity

        # 下述为了减小用户锁的开销
        self._shards = max(1, int(shards)) # 默认分片数最少1
        self._locks = [asyncio.Lock() for _ in range(self._shards)] # 构建分片锁
        self._buckets_maps = [dict() for _ in range(self._shards)] # 存储对应的64个dict,对应的用户ID-访问对象和最后的访问时间

        #
        self._ttl_ns = int(bucket_ttl_sec) * NS # 默认30分,令牌桶的存货时间，如果没有就清理
        self._cleanup_interval_ns = int(cleanup_interval_sec) * NS #  清理间隔，每10s查看是否有需要的呢?-实际上这个也是依托请求来计算的
        now = time.monotonic_ns()
        # 高并发所必需的要求 - 分片记录对应的时间
        self._next_cleanup_ns = [now + self._cleanup_interval_ns for _ in range(self._shards)] # 设置对应的清理时间

    def _user_idx(self, user_id: str) -> int:
        return abs(hash(user_id)) % self._shards

    def _cleanup_shard(self, shard: int, now_ns: int): # 清理桶,使用桶的分片索引和当前时间
        # 获取碎片索引shard和当前的时间ns
        if now_ns < self._next_cleanup_ns[shard]: # 如果当前的时间小于下一个清理时间-跳过
            return
        # 大于对应的清理时间-赋值新的间隔时间
        self._next_cleanup_ns[shard] = now_ns + self._cleanup_interval_ns # 重新赋值时间

        m = self._buckets_maps[shard] # 获取该用户的访问时间
        expired_list = [uid for uid, (_, last_seen) in m.items() if now_ns - last_seen > self._ttl_ns] # 遍历对应的分片并查看呢是否有用户过期
        for uid in expired_list:
            m.pop(uid, None) # 超出弹出

    async def intercept_service(self, continuation, handler_call_details):
        method_name = handler_call_details.method.split("/")[-1]
        if method_name in self.skip_methods:
            return await continuation(handler_call_details)
        # 上述跳过
        try:
            metadata = dict(handler_call_details.invocation_metadata or [])
            user_id = metadata.get(self.user_id_metadata_key) or "anonymous"
        except KeyError:
            logger.warning("UserRateLimit: 用户元数据用户id不存在")
            handler = await continuation(handler_call_details)
            return _abort_like_handler(
                handler,
                grpc.StatusCode.UNAUTHENTICATED,
                "无法获取用户id等元数据")
        except Exception as e:
            logger.warning(f"UserRateLimit: 获取用户元数据时出错: {e}")
            handler = await continuation(handler_call_details)
            return _abort_like_handler(
                handler,
                grpc.StatusCode.UNKNOWN,
                f"获取用户元数据时出错: {e}")
        # 上述获取到用户id - 查找对应的分片桶
        shard = self._user_idx(user_id)
        async with self._locks[shard]:
            now_ns = time.monotonic_ns()
            self._cleanup_shard(shard, now_ns) # 首先先清理过期的令牌桶

            m = self._buckets_maps[shard] # 获取分片的字典
            entry = m.get(user_id) # 获取用户id对应的令牌桶和最后访问时间
            if entry is None: # 如果不存在该用户
                # 创建对应的令牌桶以及对应的过期时间
                bucket = TokenBucket(self._rate_per_sec, self._capacity) # 创建对应的令牌桶，查看对应的
                m[user_id] = (bucket, now_ns)
            else:
                bucket, _last_seen = entry # 获取对应的值
                m[user_id] = (bucket, now_ns) # 重新赋值过期时间

            allowed = bucket.try_take_token(1)
        # 判断本身用户桶
        if not allowed:
            logger.warning(f"UserRateLimit: triggered, user={user_id}, method={method_name}")
            handler = await continuation(handler_call_details)
            return _abort_like_handler(handler, grpc.StatusCode.RESOURCE_EXHAUSTED, f"请求过于频繁，请稍后再试（用户限流: {user_id}）")

        return await continuation(handler_call_details)

