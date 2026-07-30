"""LLM 调用封装：支持 Ollama（本地开发）/ DeepSeek API（生产）"""

import time
import httpx
from app.config import settings
from app.logger import log


def _parse_response(response: dict) -> str:
    """兼容 Ollama 和 OpenAI 格式的响应解析"""
    # Ollama 格式: {"message": {"content": "..."}}
    if "message" in response:
        return response["message"].get("content", "")
    # OpenAI / DeepSeek 格式: {"choices": [{"message": {"content": "..."}}]}
    if "choices" in response and len(response["choices"]) > 0:
        return response["choices"][0].get("message", {}).get("content", "")
    log.error("Unknown response format: %s", str(response)[:200])
    return ""


def call_llm(prompt: str, system_prompt: str = "", max_retries: int = 2) -> str:
    """
    调用 LLM，返回文本回复

    通过配置 LLM_API_ENDPOINT 切换服务商:
        Ollama  : http://localhost:11434/api/chat
        DeepSeek: https://api.deepseek.com/v1/chat/completions
    """
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    headers = {
        "Content-Type": "application/json",
    }
    if settings.LLM_API_KEY:
        headers["Authorization"] = f"Bearer {settings.LLM_API_KEY}"

    for attempt in range(max_retries + 1):
        try:
            response = httpx.post(
                settings.LLM_API_ENDPOINT,
                json={
                    "model": settings.LLM_MODEL,
                    "messages": messages,
                    "stream": False,
                    "temperature": 0.3,
                    "max_tokens": 512,
                },
                timeout=60,
            )
            response.raise_for_status()
            result = _parse_response(response.json())
            if result:
                return result

        except httpx.TimeoutException:
            log.warning("LLM timeout (attempt %d/%d)", attempt + 1, max_retries + 1)
        except httpx.HTTPStatusError as e:
            log.warning("LLM HTTP %s (attempt %d/%d)", e.response.status_code, attempt + 1, max_retries + 1)
        except Exception as e:
            log.warning("LLM error: %s (attempt %d/%d)", e, attempt + 1, max_retries + 1)

        if attempt < max_retries:
            time.sleep(2 ** attempt)  # 指数退避：1s → 2s

    log.error("LLM call failed after %d retries", max_retries)
    return ""

def call_llm_with_messages(messages: list[dict], max_retries: int = 2) -> str:
    """
    调用 LLM，传入完整消息列表（包含 system / user / assistant）

    用于多轮对话场景，保留全部上下文。
    """
    headers = {
        "Content-Type": "application/json",
    }
    if settings.LLM_API_KEY:
        headers["Authorization"] = f"Bearer {settings.LLM_API_KEY}"

    body = {
        "model": settings.LLM_MODEL,
        "messages": messages,
        "stream": False,
        "temperature": 0.3,
        "max_tokens": 1024,
    }

    for attempt in range(max_retries + 1):
        try:
            response = httpx.post(
                settings.LLM_API_ENDPOINT,
                json = body,
                headers=headers,
                timeout = 60,
            )
            response.raise_for_status()
            result = _parse_response(response.json())
            if result:
                return result
                
        except httpx.TimeoutException:
            log.warning("LLM timeout (attempt %d/%d)", attempt + 1, max_retries + 1)
        except httpx.HTTPStatusError as e:
            log.warning("LLM HTTP %s (attempt %d/%d)", e.response.status_code, attempt + 1, max_retries + 1)
        except Exception as e:
            log.warning("LLM error: %s (attempt %d/%d)", e, attempt + 1, max_retries + 1)

        if attempt < max_retries:
            time.sleep(2 ** attempt)

    log.error("LLM call failed after %d retries", max_retries)
    return ""