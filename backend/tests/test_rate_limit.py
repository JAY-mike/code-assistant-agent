"""Rate-limit middleware tests without a Redis server."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.middleware import RateLimitMiddleware


class FakePipeline:
    def __init__(self, store):
        self.store = store
        self.operations = []

    def zremrangebyscore(self, key, minimum, maximum):
        self.operations.append(("zremrangebyscore", key, minimum, maximum))
        return self

    def zadd(self, key, values):
        self.operations.append(("zadd", key, values))
        return self

    def zcard(self, key):
        self.operations.append(("zcard", key))
        return self

    def expire(self, key, seconds):
        self.operations.append(("expire", key, seconds))
        return self

    def execute(self):
        results = []
        for operation in self.operations:
            command, key, *args = operation
            values = self.store.setdefault(key, {})
            if command == "zremrangebyscore":
                minimum, maximum = args
                expired = [member for member, score in values.items() if minimum <= score <= maximum]
                for member in expired:
                    del values[member]
                results.append(len(expired))
            elif command == "zadd":
                values.update(args[0])
                results.append(len(args[0]))
            elif command == "zcard":
                results.append(len(values))
            else:
                results.append(True)
        return results


class FakeRedis:
    def __init__(self):
        self.store = {}

    def pipeline(self):
        return FakePipeline(self.store)


def test_second_api_request_is_rate_limited():
    app = FastAPI()
    app.add_middleware(
        RateLimitMiddleware,
        rate_limit=1,
        window_seconds=60,
        redis_client=FakeRedis(),
    )

    @app.get("/api/ping")
    async def ping():
        return {"ok": True}

    with TestClient(app) as client:
        assert client.get("/api/ping").status_code == 200
        assert client.get("/api/ping").status_code == 429
