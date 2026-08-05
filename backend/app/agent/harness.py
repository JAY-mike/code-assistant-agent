"""Agent Harness：工具注册 + ReAct 循环 + 执行轨迹记录"""

import json
import asyncio
from typing import Optional
from app.agent.llm import call_llm_with_messages
from app.agent.prompt import REACT_SYSTEM_PROMPT, build_tool_descriptions
from app.agent.tools import AVAILABLE_TOOLS
from app.logger import log


def _extract_json_action(text: str) -> Optional[dict]:
    """从文本中提取第一个包含 'name' 字段的有效 JSON 对象"""
    depth = 0
    start = -1
    for i, ch in enumerate(text):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start >= 0:
                try:
                    obj = json.loads(text[start:i+1])
                    if "name" in obj:
                        return obj
                except json.JSONDecodeError:
                    pass
                start = -1
    return None


class AgentHarness:
    def __init__(self, tools: list = None, session_id: str = "default"):
        self.tools = tools or AVAILABLE_TOOLS
        self.tool_map = {t.name: t for t in self.tools}
        self.history = []
        self.session_id = session_id
        self.conversation_history = []  # 多轮对话：保存历史 Q&A

    def restore_history(self, history: list[dict]):
        """从数据库恢复对话历史"""
        self.conversation_history = history

    async def _log_step(self, step: int, thought: str,
                        action_name: str = None, action_args: str = None,
                        observation: str = None):
        """异步写 Agent 决策日志到数据库"""
        try:
            from app.database import async_session_factory
            from app.models.agent_log import AgentLog

            async with async_session_factory() as session:
                session.add(AgentLog(
                    session_id=self.session_id,
                    step_number=step,
                    thought=thought[:500],
                    action_name=action_name,
                    action_args=action_args,
                    observation=observation[:200] if observation else None,
                ))
                await session.commit()
        except Exception as e:
            log.warning("Failed to log agent step: %s", e)

    def _schedule_log(self, step: int, thought: str,
                      action_name: str = None, action_args: str = None,
                      observation: str = None):
        """在合适的上下文里调度异步日志：有事件循环用 create_task，否则 asyncio.run"""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            # 后台线程，没有运行中的事件循环 → 独立跑
            asyncio.run(self._log_step(
                step=step, thought=thought,
                action_name=action_name, action_args=action_args,
                observation=observation,
            ))
        else:
            loop.create_task(self._log_step(
                step=step, thought=thought,
                action_name=action_name, action_args=action_args,
                observation=observation,
            ))

    def get_tool_description(self) -> str:
        return build_tool_descriptions(self.tools)

    def execute_tool(self, name: str, args: dict) -> str:
        tool = self.tool_map.get(name)
        if not tool:
            return f"Error: unknown tool '{name}' "
        log.info("  Tool call : %s(%s)", name, json.dumps(args))
        result = tool.execute(**args)
        log.info("  Tool result: %s...", result[:80].replace("\n", " "))
        return result

    def run(self, user_input: str, max_step: int = 6) -> str:
        system_prompt = REACT_SYSTEM_PROMPT.format(
            tool_descriptions=self.get_tool_description()
        )

        # 构建 messages：保留历史上下文，追加新问题
        messages = [{"role": "system", "content": system_prompt}]
        for msg in self.conversation_history:
            messages.append(msg)
        messages.append({"role": "user", "content": user_input})

        for step in range(max_step):
            log.info("Step %d: calling LLM...", step + 1)

            response = call_llm_with_messages(messages)

            # 检查 LLM 是否返回空
            if not response:
                return "Error: LLM failed to respond after retries. Please check the API."

            messages.append({"role": "assistant", "content": response})
            self.history.append({"step": step, "response": response})

            # 检查是否包含 Action JSON（支持嵌套花括号）
            action = _extract_json_action(response)
            if action:
                try:
                    obs = self.execute_tool(action["name"], action.get("args", {}))
                    messages.append({"role": "user", "content": f"Observation: {obs}"})

                    # 记录决策日志（异步，不阻塞循环）
                    self._schedule_log(
                        step=step + 1,
                        thought=response,
                        action_name=action["name"],
                        action_args=json.dumps(action.get("args", {})),
                        observation=obs,
                    )

                    continue
                except (json.JSONDecodeError, KeyError) as e:
                    messages.append({"role": "user", "content": f"Observation: JSON parse error: {e}"})

                    self._schedule_log(
                        step=step + 1, thought=response,
                        action_name="parse_error",
                        action_args=str(e),
                        observation=None,
                    )

                    continue

            # 没有 Action JSON → 认为是最终答案
            self._schedule_log(
                step=step + 1, thought=response,
                action_name="answer", action_args=None,
                observation=None,
            )


            # 保存本轮问答到历史（供下一轮使用）
            self.conversation_history.append({"role": "user", "content": user_input})
            self.conversation_history.append({"role": "assistant", "content": response.strip()})

            return response.strip()


        return "Max steps reached. Please refine your question."
