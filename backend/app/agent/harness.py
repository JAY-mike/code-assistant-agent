"""Tool-calling Agent harness with bounded execution and trace logging."""

import asyncio
import json
from threading import Event
from time import monotonic

from pydantic import ValidationError

from app.agent.llm import call_llm_with_tools
from app.agent.llm import call_llm_with_messages
from app.agent.llm import call_llm_with_messages_stream
from app.config import settings
from app.agent.prompt import build_system_prompt
from app.rag.knowledge_bases import DEFAULT_KNOWLEDGE_BASE, get_knowledge_base
from app.logger import log


class AgentCancelled(Exception):
    """Raised when the connected streaming client has gone away."""


class AgentHarness:
    def __init__(
        self,
        tools: list = None,
        session_id: str = "default",
        knowledge_base_id: str = DEFAULT_KNOWLEDGE_BASE,
    ):
        self.knowledge_base = get_knowledge_base(knowledge_base_id)
        if tools is None:
            # Keep protocol tests and application startup independent of retrieval dependencies.
            from app.agent.tools import build_tools
            tools = build_tools(knowledge_base_id)
        self.tools = tools
        self.tool_map = {tool.name: tool for tool in self.tools}
        self.history = []
        self.execution_trace = []
        self.metrics = {}
        self.session_id = session_id
        self.conversation_history = []

    def restore_history(self, history: list[dict]):
        """Restore persisted user and final-assistant messages."""
        self.conversation_history = history

    async def _log_step(
        self,
        step: int,
        thought: str,
        action_name: str = None,
        action_args: str = None,
        observation: str = None,
    ):
        """Persist an execution summary without storing a chain of thought."""
        try:
            from app.database import async_session_factory
            from app.models.agent_log import AgentLog

            async with async_session_factory() as session:
                session.add(
                    AgentLog(
                        session_id=self.session_id,
                        step_number=step,
                        thought=thought,
                        action_name=action_name,
                        action_args=action_args,
                        observation=observation[:200] if observation else None,
                    )
                )
                await session.commit()
        except Exception as exc:
            log.warning("Failed to log agent step: %s", exc)

    def _schedule_log(self, **kwargs):
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            asyncio.run(self._log_step(**kwargs))
        else:
            loop.create_task(self._log_step(**kwargs))

    @staticmethod
    def _emit(emit, event: str, data: dict):
        if emit is None:
            return
        try:
            emit(event, data)
        except Exception:
            log.exception("Agent event callback failed")

    def _check_cancelled(self):
        if self._cancel_event and self._cancel_event.is_set():
            raise AgentCancelled("Agent request cancelled by client disconnect")

    def get_tool_schemas(self) -> list[dict]:
        return [tool.function_schema() for tool in self.tools]

    def execute_tool(self, name: str, args: dict) -> tuple[str, dict]:
        tool = self.tool_map.get(name)
        if tool is None:
            raise ValueError(f"Unknown tool '{name}'")
        if not isinstance(args, dict):
            raise ValueError("Tool arguments must be a JSON object")

        validated_args = tool.validate_args(args)
        log.info("Tool call: %s(%s)", name, json.dumps(validated_args, ensure_ascii=False))
        result = tool.execute(**validated_args)
        log.info("Tool result: %s...", result[:80].replace("\n", " "))
        return result, validated_args

    @staticmethod
    def _tool_error(exc: Exception) -> str:
        return json.dumps({"error": str(exc)}, ensure_ascii=False)

    def _execute_tool_call(
        self, step: int, tool_call: dict, executed_actions: set[str],
    ) -> dict:
        """Validate, execute, trace, and convert one provider tool call."""
        function = tool_call.get("function", {})
        name = function.get("name", "")
        raw_args = function.get("arguments", "{}")
        action_args = (
            raw_args if isinstance(raw_args, str) else json.dumps(raw_args, ensure_ascii=False)
        )
        tool = None

        try:
            args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
            tool = self.tool_map.get(name)
            if tool is None:
                raise ValueError(f"Unknown tool '{name}'")
            trace_args = tool.validate_args(args)
            fingerprint = json.dumps(
                {"name": name, "arguments": trace_args},
                ensure_ascii=False,
                sort_keys=True,
            )
            if fingerprint in executed_actions:
                raise ValueError("Repeated tool call is not allowed; use the previous observation.")
            started_at = monotonic()
            try:
                observation, trace_args = self.execute_tool(name, trace_args)
            finally:
                self.metrics["tool_latency_ms"] += (monotonic() - started_at) * 1000
                self.metrics["tool_call_count"] += 1
            executed_actions.add(fingerprint)
            status = "completed"
        except (json.JSONDecodeError, ValidationError, ValueError) as exc:
            observation = self._tool_error(exc)
            trace_args = None
            status = "rejected"
        except Exception:
            log.exception("Tool '%s' failed", name)
            observation = json.dumps({"error": "Tool execution failed"})
            trace_args = None
            status = "failed"

        trace = {
            "step": step,
            "tool_name": name or "invalid_tool_call",
            "arguments": trace_args,
            "status": status,
            "observation": observation[:200],
        }
        citations = getattr(tool, "last_citations", []) if tool else []
        if citations:
            trace["citations"] = citations
            self._merge_citations(citations)
        self.execution_trace.append(trace)
        self._schedule_log(
            step=step,
            thought="tool_call",
            action_name=name or "invalid_tool_call",
            action_args=action_args,
            observation=observation,
        )
        return {
            "role": "tool",
            "tool_call_id": tool_call.get("id", ""),
            "content": observation,
        }

    def _merge_citations(self, citations: list[dict]):
        known = {item["source"] for item in self.citations}
        for citation in citations:
            if citation["source"] not in known:
                self.citations.append(citation)
                known.add(citation["source"])

    def _fallback_answer(self, reason: str) -> str:
        observations = [
            item["observation"]
            for item in self.execution_trace
            if item.get("status") == "completed" and item.get("observation")
        ]
        if observations:
            evidence = "\n\n".join(observations[-2:])
            return (
                f"本轮已完成检索，但{reason}，未能生成完整归纳。"
                f"以下是已获得的相关证据：\n{evidence}"
            )
        return f"本轮处理未能完成：{reason}。请缩小问题范围后重试。"

    def _call_coordinator_llm(self, call, *args, **kwargs):
        started_at = monotonic()
        try:
            return call(*args, **kwargs)
        finally:
            self.metrics["coordinator_llm_latency_ms"] += (
                monotonic() - started_at
            ) * 1000
            self.metrics["coordinator_llm_call_count"] += 1

    def _save_answer(
        self,
        user_input: str,
        answer: str,
        step: int,
        emit=None,
        emit_answer: bool = True,
    ) -> str:
        if emit_answer:
            self._emit(emit, "delta", {"text": answer})
        self._schedule_log(step=step, thought="final_answer", action_name="answer")
        self.conversation_history.append({"role": "user", "content": user_input})
        self.conversation_history.append({"role": "assistant", "content": answer})
        return answer

    def _finish_from_observations(
        self,
        messages: list[dict],
        user_input: str,
        step: int,
        reason: str,
        emit=None,
    ) -> str:
        """Ask for one bounded final synthesis before exposing raw evidence."""
        self._check_cancelled()
        if emit is None:
            emit = self._event_emitter
        remaining = self._deadline - monotonic()
        if remaining > 0.2:
            final_messages = list(messages)
            final_messages.append({
                "role": "user",
                "content": (
                    f"{reason} 现在必须停止调用工具。请仅依据已有 tool observation，"
                    "用中文直接回答原问题；如果证据不足，请明确说明，不要编造。"
                ),
            })
            answer = self._call_coordinator_llm(
                call_llm_with_messages,
                final_messages,
                max_retries=0,
                timeout_seconds=min(settings.AGENT_LLM_TIMEOUT_SECONDS, remaining),
                cancel_event=self._cancel_event,
            )
            if answer.strip():
                return self._save_answer(user_input, answer.strip(), step, emit=emit)

        answer = self._fallback_answer(reason)
        return self._save_answer(user_input, answer, step, emit=emit)

    def _finish_streaming_from_observations(
        self,
        messages: list[dict],
        user_input: str,
        step: int,
        emit,
    ) -> str:
        remaining = self._deadline - monotonic()
        if remaining <= 0.2:
            answer = self._fallback_answer("已达到本轮时间预算")
            return self._save_answer(user_input, answer, step, emit=emit)

        final_messages = list(messages)
        final_messages.append({
            "role": "user",
            "content": (
                "请停止调用工具，仅依据已有 tool observation 回答原问题。"
                "使用中文，证据不足时明确说明，不要编造。"
            ),
        })
        parts = []

        def on_delta(text: str):
            parts.append(text)
            self._emit(emit, "delta", {"text": text})

        answer = self._call_coordinator_llm(
            call_llm_with_messages_stream,
            final_messages,
            on_delta=on_delta,
            timeout_seconds=min(settings.AGENT_LLM_TIMEOUT_SECONDS, remaining),
            cancel_event=self._cancel_event,
        ).strip()
        self._check_cancelled()
        if not answer:
            answer = "".join(parts).strip()
        if not answer:
            answer = self._fallback_answer("回答生成超时或暂时不可用")
            self._emit(emit, "delta", {"text": answer})
        return self._save_answer(
            user_input,
            answer,
            step,
            emit=emit,
            emit_answer=False,
        )

    def run(
        self,
        user_input: str,
        max_step: int | None = None,
        emit=None,
        stream_final: bool = False,
        cancel_event: Event | None = None,
    ) -> str:
        self.metrics = {
            "agent_latency_ms": 0.0,
            "coordinator_llm_latency_ms": 0.0,
            "tool_latency_ms": 0.0,
            "coordinator_llm_call_count": 0,
            "tool_call_count": 0,
        }
        started_at = monotonic()
        try:
            return self._run(
                user_input,
                max_step=max_step,
                emit=emit,
                stream_final=stream_final,
                cancel_event=cancel_event,
            )
        finally:
            self.metrics["agent_latency_ms"] = round(
                (monotonic() - started_at) * 1000, 2
            )
            for key in ("coordinator_llm_latency_ms", "tool_latency_ms"):
                self.metrics[key] = round(self.metrics[key], 2)

    def _run(
        self,
        user_input: str,
        max_step: int | None = None,
        emit=None,
        stream_final: bool = False,
        cancel_event: Event | None = None,
    ) -> str:
        self.execution_trace = []
        self.citations = []
        self._event_emitter = emit
        self._cancel_event = cancel_event
        max_step = min(max_step or settings.AGENT_MAX_STEPS, settings.AGENT_MAX_STEPS)
        self._deadline = monotonic() + settings.AGENT_MAX_DURATION_SECONDS
        messages = [{"role": "system", "content": build_system_prompt(self.knowledge_base.label)}]
        messages.extend(self.conversation_history)
        messages.append({"role": "user", "content": user_input})
        executed_actions = set()

        for step in range(max_step):
            self._check_cancelled()
            remaining = self._deadline - monotonic()
            if remaining <= 0.2:
                return self._finish_from_observations(
                    messages, user_input, step + 1, "已达到本轮时间预算"
                )
            self._emit(emit, "status", {"message": f"正在处理第 {step + 1} 步..."})
            log.info("Agent step %d: calling LLM", step + 1)
            response = self._call_coordinator_llm(
                call_llm_with_tools,
                messages,
                self.get_tool_schemas(),
                max_retries=settings.AGENT_LLM_MAX_RETRIES,
                timeout_seconds=min(settings.AGENT_LLM_TIMEOUT_SECONDS, remaining),
                cancel_event=cancel_event,
            )
            if response is None:
                return self._finish_from_observations(
                    messages, user_input, step + 1, "模型调用超时或暂时不可用"
                )

            messages.append(response)
            self.history.append({"step": step + 1, "response": response})
            tool_calls = response["tool_calls"]

            if tool_calls:
                self._emit(emit, "status", {"message": "正在执行工具..."})
                for tool_call in tool_calls:
                    messages.append(self._execute_tool_call(step + 1, tool_call, executed_actions))
                    self._emit(emit, "trace", {"trace": self.execution_trace[-1]})
                    self._check_cancelled()
                if stream_final:
                    self._emit(emit, "status", {"message": "正在根据检索结果生成回答..."})
                continue

            answer = (response["content"] or "").strip()
            if not answer:
                return self._finish_from_observations(
                    messages, user_input, step + 1, "模型未返回最终文本"
                )

            if stream_final and self.execution_trace:
                self._emit(emit, "status", {"message": "正在流式输出回答..."})
                return self._finish_streaming_from_observations(
                    messages, user_input, step + 1, emit
                )
            return self._save_answer(user_input, answer, step + 1, emit=emit)

        if stream_final and self.execution_trace:
            self._emit(emit, "status", {"message": "正在流式输出回答..."})
            return self._finish_streaming_from_observations(
                messages, user_input, max_step, emit
            )

        return self._finish_from_observations(
            messages, user_input, max_step, f"已达到最多 {max_step} 步工具调用"
        )
