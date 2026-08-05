"""Shared test configuration that keeps tests out of the development database."""

import os


os.environ["SKIP_SECRET_VALIDATION"] = "1"
os.environ["JWT_SECRET"] = "test-secret-only-for-ci-0123456789abcdef"
os.environ["LLM_API_KEY"] = "sk-test-only-for-ci-not-real"
os.environ["MYSQL_HOST"] = "127.0.0.1"
os.environ["MYSQL_PORT"] = "3306"
os.environ["MYSQL_USER"] = "root"
os.environ["MYSQL_PASSWORD"] = "123456"
os.environ["MYSQL_DATABASE"] = "code_assistant_test"
os.environ["REDIS_HOST"] = "127.0.0.1"
os.environ["REDIS_PORT"] = "6379"
