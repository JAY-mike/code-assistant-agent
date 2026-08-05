"""Redis 滑动窗口限流中间件"""

import time
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from app.config import settings
from app.logger import log


class RateLimitMiddleware(BaseHTTPMiddleware):
    """滑动窗口限流：每用户每分钟最多 rate_limit 次请求"""

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
        """从请求里识别客户端：优先用用户，其次用 IP"""
        user = request.state.user if hasattr(request.state, "user") else None
        if user:
            return f"user:{user.id}"
        return f"ip:{request.client.host}"

    async def dispatch(self, request: Request, call_next):
        if self.redis is None:
            return await call_next(request)

        # 只对 API 路径限流，跳过静态资源和文档
        if not request.url.path.startswith("/api/"):
            return await call_next(request)

        client = self._client_key(request)
        window_start = int(time.time() // self.window_seconds)
        key = f"ratelimit:{client}:{window_start}"

        try:
            count = self.redis.incr(key)
            if count == 1:
                self.redis.expire(key, self.window_seconds + 1)

            if count > self.rate_limit:
                raise HTTPException(status_code=429, detail="Rate limit exceeded")
        except HTTPException:
            raise
        except Exception as e:
            log.warning("Rate limit check failed: %s", e)

        return await call_next(request)