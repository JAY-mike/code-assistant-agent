"""JWT 鉴权：创建/验证 token、密码哈希、依赖注入"""

import datetime
from datetime import UTC, timedelta
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
import bcrypt
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.config import settings
from app.database import get_db
from app.models.user import User

security = HTTPBearer()

# JWT 配置直接从 settings 读取，或硬编码默认值
SECRET_KEY = settings.JWT_SECRET
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 小时
REFRESH_TOKEN_EXPIRE_DAYS = 7

def hash_password(password: str) -> str:
    """bcrypt 哈希密码（原生 API）"""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证密码"""
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8"),
        )
    except ValueError:
        return False

def create_access_token(data: dict) -> str:
    """创建访问 token（短期）"""

    to_encode = data.copy()
    expire = datetime.datetime.now(UTC) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire , "type": "access"})
    return jwt.encode(to_encode , SECRET_KEY , algorithm=ALGORITHM)

def create_refresh_token(data: dict) -> str:
    """创建刷新 token（长期）"""

    to_encode = data.copy()
    expire = datetime.datetime.now(UTC) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def decode_token(token: str) -> dict:
    """解码 token，失败抛 401"""

    try:
        payload = jwt.decode(token, SECRET_KEY , algorithms=[ALGORITHM])
        return payload

    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expire token",
        )

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db:AsyncSession = Depends(get_db),
) -> User:
    """FastAPI 依赖注入：从请求头获取当前登录用户"""
    if is_token_blacklisted(credentials.credentials):
        raise HTTPException(status_code=401, detail="Token has been revoked")
    payload = decode_token(credentials.credentials)
    username = payload.get("sub")
    if not username:
        raise HTTPException(status_code=401 , detail="Invalid token") 

    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")
    return user

from app.clients import get_redis_client

def _get_redis():
    return get_redis_client()


def blacklist_token(token: str, expire_seconds: int):
    """把 token 加入 Redis 黑名单"""
    try:
        r = _get_redis()
        if r is None:
            return
        r.setex(f"blacklist:{token}", expire_seconds, "1")
    except Exception:
        pass


def is_token_blacklisted(token: str) -> bool:
    """检查 token 是否在黑名单中"""
    try:
        r = _get_redis()
        if r is None:
            return False
        return bool(r.exists(f"blacklist:{token}"))
    except Exception:
        return False
