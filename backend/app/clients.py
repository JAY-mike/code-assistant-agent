"""Process-wide clients shared by cache, rate limiting, and retrieval."""

from threading import Lock

import redis as redis_lib
from redis.backoff import NoBackoff
from redis.retry import Retry

from app.config import settings
from app.logger import log

_redis_client = None
_redis_initialized = False
_redis_lock = Lock()


def get_redis_client():
    """Create one Redis client/connection pool for this backend process."""
    global _redis_client, _redis_initialized
    with _redis_lock:
        if _redis_initialized:
            return _redis_client

        _redis_initialized = True
        try:
            client = redis_lib.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                db=0,
                decode_responses=True,
                protocol=2,
                socket_connect_timeout=0.2,
                socket_timeout=0.2,
                retry=Retry(NoBackoff(), retries=0),
            )
            client.ping()
            _redis_client = client
        except Exception as exc:
            log.warning("Redis unavailable, shared client disabled: %s", exc)
            _redis_client = None
        return _redis_client
