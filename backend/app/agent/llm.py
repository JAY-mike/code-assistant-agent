"""LLM client for text completions and OpenAI-compatible tool calls."""

import json
import time
from collections.abc import Callable
from threading import Event

import httpx

from app.config import settings
from app.logger import log


def _headers() -> dict:
    headers = {"Content-Type": "application/json"}
    if settings.LLM_API_KEY:
        headers["Authorization"] = f"Bearer {settings.LLM_API_KEY}"
    return headers


def _parse_response(response: dict) -> str:
    """Parse Ollama and OpenAI-compatible text responses."""
    if "message" in response:
        return response["message"].get("content", "")
    if response.get("choices"):
        return response["choices"][0].get("message", {}).get("content", "") or ""
    log.error("Unknown response format: %s", str(response)[:200])
    return ""


def _parse_assistant_message(response: dict) -> dict | None:
    """Extract an assistant message and preserve the provider's tool calls."""
    choices = response.get("choices", [])
    if not choices:
        log.error("Tool-calling response has no choices: %s", str(response)[:200])
        return None

    message = choices[0].get("message")
    if not isinstance(message, dict):
        log.error("Tool-calling response has no assistant message: %s", str(response)[:200])
        return None

    return {
        "role": "assistant",
        "content": message.get("content"),
        "tool_calls": message.get("tool_calls") or [],
    }


def _post_with_retries(
    body: dict,
    max_retries: int,
    timeout_seconds: float = 60,
    cancel_event: Event | None = None,
) -> dict | None:
    for attempt in range(max_retries + 1):
        if cancel_event and cancel_event.is_set():
            log.info("LLM call cancelled before attempt")
            return None
        try:
            response = httpx.post(
                settings.LLM_API_ENDPOINT,
                json=body,
                headers=_headers(),
                timeout=timeout_seconds,
            )
            response.raise_for_status()
            return response.json()
        except httpx.TimeoutException:
            log.warning("LLM timeout (attempt %d/%d)", attempt + 1, max_retries + 1)
        except httpx.HTTPStatusError as exc:
            log.warning(
                "LLM HTTP %s (attempt %d/%d)",
                exc.response.status_code,
                attempt + 1,
                max_retries + 1,
            )
        except Exception as exc:
            log.warning("LLM error: %s (attempt %d/%d)", exc, attempt + 1, max_retries + 1)

        if attempt < max_retries:
            time.sleep(2 ** attempt)

    log.error("LLM call failed after %d retries", max_retries)
    return None


def call_llm(
    prompt: str,
    system_prompt: str = "",
    max_retries: int = 2,
    timeout_seconds: float = 60,
    cancel_event: Event | None = None,
) -> str:
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    response = _post_with_retries(
        {
            "model": settings.LLM_MODEL,
            "messages": messages,
            "stream": False,
            "temperature": 0.3,
            "max_tokens": 512,
        },
        max_retries,
        timeout_seconds,
        cancel_event,
    )
    return _parse_response(response) if response is not None else ""


def call_llm_with_messages(
    messages: list[dict],
    max_retries: int = 2,
    timeout_seconds: float = 60,
    cancel_event: Event | None = None,
) -> str:
    response = _post_with_retries(
        {
            "model": settings.LLM_MODEL,
            "messages": messages,
            "stream": False,
            "temperature": 0.3,
            "max_tokens": 1024,
        },
        max_retries,
        timeout_seconds,
        cancel_event,
    )
    return _parse_response(response) if response is not None else ""


def call_llm_with_messages_stream(
    messages: list[dict],
    on_delta: Callable[[str], None],
    timeout_seconds: float = 60,
    cancel_event: Event | None = None,
) -> str:
    """Stream an OpenAI-compatible completion and return the assembled text."""
    body = {
        "model": settings.LLM_MODEL,
        "messages": messages,
        "stream": True,
        "temperature": 0.3,
        "max_tokens": 1024,
    }
    chunks = []
    try:
        with httpx.stream(
            "POST",
            settings.LLM_API_ENDPOINT,
            json=body,
            headers=_headers(),
            timeout=timeout_seconds,
        ) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if cancel_event and cancel_event.is_set():
                    log.info("Streaming LLM response cancelled")
                    break
                if not line or not line.startswith("data:"):
                    continue
                data = line.removeprefix("data:").strip()
                if data == "[DONE]":
                    break
                try:
                    payload = json.loads(data)
                    delta = payload["choices"][0].get("delta", {}).get("content") or ""
                except (IndexError, KeyError, TypeError, json.JSONDecodeError):
                    continue
                if delta:
                    chunks.append(delta)
                    on_delta(delta)
    except httpx.TimeoutException:
        log.warning("Streaming LLM response timed out")
    except httpx.HTTPStatusError as exc:
        log.warning("Streaming LLM HTTP %s", exc.response.status_code)
    except Exception as exc:
        log.warning("Streaming LLM error: %s", exc)

    return "".join(chunks)


def call_llm_with_tools(
    messages: list[dict],
    tools: list[dict],
    max_retries: int = 2,
    timeout_seconds: float = 60,
    cancel_event: Event | None = None,
) -> dict | None:
    """Call an OpenAI-compatible endpoint and return a structured message."""
    response = _post_with_retries(
        {
            "model": settings.LLM_MODEL,
            "messages": messages,
            "tools": tools,
            "tool_choice": "auto",
            "stream": False,
            "temperature": 0.3,
            "max_tokens": 1024,
        },
        max_retries,
        timeout_seconds,
        cancel_event,
    )
    return _parse_assistant_message(response) if response is not None else None
