"""统一日志配置"""

import logging
import sys


def setup_logger(name: str = "code_assistant") -> logging.Logger:
    """创建统一格式的 logger"""
    logger = logging.getLogger(name)

    if not logger.handlers:
        logger.setLevel(logging.INFO)

        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(logging.INFO)

        formatter = logging.Formatter(
            "[%(name)s] %(levelname)s %(message)s",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger


# 全局默认 logger
log = setup_logger()
