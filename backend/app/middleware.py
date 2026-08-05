"""Redis 滑动窗口限流中间件（基于 ZSET）"""

import time
import uuid

from fastapi import Request
from starlette.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from app.config import settings
from app.logger import log


class RateLimitMiddleware(BaseHTTPMiddleware):
    """滑动窗口限流：每客户端在 window_seconds 内最多 rate_limit 次请求

    用 Redis ZSET 实现真正的滑动窗口：每个请求时间戳作为一个 member，
    每次检查时删除窗口外的旧记录，统计窗口内的数量。
    相比固定窗口（time()//window），滑动窗口不会在窗口边界产生突刺。
    """

    def __init__(self, app, rate_limit: int = 60, window_seconds: int = 60):
        super().__init__(app)
        self.rate_limit = rate_limit
        self.window_seconds = window_seconds
        self.redis = None
        try:
            import redis as redis_lib
            self.redis = redis_lib.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                db=0,
                decode_responses=True,
                protocol=2,
            )
            self.redis.ping()
        except Exception as e:
            log.warning("Redis unavailable, rate limiting disabled: %s", e)

    def _client_key(self, request: Request) -> str:
        """识别客户端：优先从 JWT 解析用户，否则退回 IP。

        注意：中间件在鉴权依赖（get_current_user）之前运行，拿不到
        request.state.user，所以这里自己解析 Authorization 头。
        """
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth[len("Bearer "):]
            try:
                from app.auth import decode_token
                payload = decode_token(token)
                if payload.get("type") == "access":
                    return f"user:{payload.get('sub', 'unknown')}"
            except Exception:
                # token 无效或过期，退回 IP 限流
                pass
        return f"ip:{request.client.host}"

    async def dispatch(self, request: Request, call_next):
        if self.redis is None:
            return await call_next(request)

        # 只对 API 路径限流，跳过静态资源和文档
        if not request.url.path.startswith("/api/"):
            return await call_next(request)

        client = self._client_key(request)
        key = f"ratelimit:{client}"

        try:
            now = time.time()
            window_start = now - self.window_seconds
            pipeline = self.redis.pipeline()
            pipeline.zremrangebyscore(key, 0, window_start)  # 删窗口外旧记录
            pipeline.zadd(key, {uuid.uuid4().hex: now})       # 加当前请求
            pipeline.zcard(key)                              # 统计窗口内数量
            pipeline.expire(key, self.window_seconds + 1)
            _, _, count, _ = pipeline.execute()

            if count > self.rate_limit:
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Rate limit exceeded"},
                )
        except Exception as e:
            log.warning("Rate limit check failed: %s", e)

        return await call_next(request)
