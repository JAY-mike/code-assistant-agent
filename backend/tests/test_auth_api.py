"""鉴权 API 集成测试：注册 / 登录 / 刷新 / 登出 / 未授权访问

用一个只挂载 auth_router 的独立 FastAPI app 测试，避免触发 chromadb
等重型依赖加载，保证 CI 快速运行。

依赖 CI 提供的 MySQL + Redis services（见 .github/workflows/ci.yml）。
"""

import pytest
import redis
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.database import engine, Base
from app.routers.auth_router import router
from app.services.conversation_service import load_history, save_message

# 独立 app，只挂 auth_router，不加载 chromadb 相关模块
app = FastAPI()
app.include_router(router, prefix="/api")


def _redis_available() -> bool:
    try:
        client = redis.Redis(
            host="127.0.0.1",
            port=6379,
            socket_connect_timeout=0.2,
            socket_timeout=0.2,
        )
        return bool(client.ping())
    except redis.RedisError:
        return False


async def _create_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def _drop_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


async def _dispose_engine():
    await engine.dispose()


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        test_client.portal.call(_create_tables)
        yield test_client
        test_client.portal.call(_drop_tables)
        test_client.portal.call(_dispose_engine)


class TestRegister:
    def test_register_success(self, client):
        resp = client.post("/api/auth/register",
                           json={"username": "alice", "password": "secret123"})
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data

    def test_register_duplicate(self, client):
        client.post("/api/auth/register",
                    json={"username": "bob", "password": "secret123"})
        resp = client.post("/api/auth/register",
                           json={"username": "bob", "password": "secret123"})
        assert resp.status_code == 400


class TestLogin:
    def test_login_success(self, client):
        client.post("/api/auth/register",
                    json={"username": "carol", "password": "secret123"})
        resp = client.post("/api/auth/login",
                           json={"username": "carol", "password": "secret123"})
        assert resp.status_code == 200
        assert "access_token" in resp.json()

    def test_login_wrong_password(self, client):
        client.post("/api/auth/register",
                    json={"username": "dave", "password": "secret123"})
        resp = client.post("/api/auth/login",
                           json={"username": "dave", "password": "wrong"})
        assert resp.status_code == 401


class TestProtected:
    def test_no_token_returns_401(self, client):
        resp = client.post("/api/auth/logout")
        assert resp.status_code == 401

    def test_invalid_token_returns_401(self, client):
        resp = client.post("/api/auth/logout",
                           headers={"Authorization": "Bearer not-a-real-token"})
        assert resp.status_code == 401


@pytest.mark.skipif(not _redis_available(), reason="requires a running Redis instance")
class TestLogoutBlacklist:
    def test_logout_revokes_token(self, client):
        # 注册登录拿 token
        client.post("/api/auth/register",
                    json={"username": "erin", "password": "secret123"})
        login = client.post("/api/auth/login",
                            json={"username": "erin", "password": "secret123"})
        token = login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 登出成功
        resp = client.post("/api/auth/logout", headers=headers)
        assert resp.status_code == 200

        # token 已进黑名单，再访问受保护接口应 401
        resp = client.post("/api/auth/logout", headers=headers)
        assert resp.status_code == 401


class TestRefresh:
    def test_refresh_returns_new_tokens(self, client):
        client.post("/api/auth/register",
                    json={"username": "frank", "password": "secret123"})
        login = client.post("/api/auth/login",
                            json={"username": "frank", "password": "secret123"})
        refresh_token = login.json()["refresh_token"]

        resp = client.post("/api/auth/refresh", params={"refresh_token": refresh_token})
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data

    def test_refresh_rejects_access_token(self, client):
        client.post("/api/auth/register",
                    json={"username": "grace", "password": "secret123"})
        login = client.post("/api/auth/login",
                            json={"username": "grace", "password": "secret123"})
        access_token = login.json()["access_token"]

        # 用 access token 当 refresh token 用，应该被拒绝
        resp = client.post("/api/auth/refresh", params={"refresh_token": access_token})
        assert resp.status_code == 401


class TestConversationIsolation:
    def test_same_session_id_is_scoped_to_user(self, client):
        client.portal.call(save_message, 1, "shared-session", "user", "alice secret")
        client.portal.call(save_message, 2, "shared-session", "user", "bob secret")

        alice_history = client.portal.call(load_history, 1, "shared-session")
        bob_history = client.portal.call(load_history, 2, "shared-session")

        assert [message["content"] for message in alice_history] == ["alice secret"]
        assert [message["content"] for message in bob_history] == ["bob secret"]
