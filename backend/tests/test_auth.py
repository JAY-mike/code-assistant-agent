"""密码哈希单元测试"""

import sys
import os

# 必须在 import app 之前设置：纯逻辑测试不需要真实密钥
os.environ.setdefault("SKIP_SECRET_VALIDATION", "1")
os.environ.setdefault("JWT_SECRET", "test-secret-only-for-ci-0123456789abcdef")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.auth import hash_password, verify_password


class TestPasswordHashing:
    def test_hash_then_verify_success(self):
        hashed = hash_password("mysecret")
        assert verify_password("mysecret", hashed) is True

    def test_wrong_password_fails(self):
        hashed = hash_password("mysecret")
        assert verify_password("wrong", hashed) is False

    def test_hash_is_different_each_time(self):
        h1 = hash_password("same")
        h2 = hash_password("same")
        assert h1 != h2  # bcrypt 每次加随机盐
