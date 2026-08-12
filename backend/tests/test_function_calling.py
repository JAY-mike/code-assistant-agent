"""Function-calling harness tests without a live LLM or database."""

from threading import Event

import pytest
from pydantic import BaseModel, Field

from app.agent import llm
from app.agent.harness import AgentCancelled, AgentHarness
from app.agent.tool_base import Tool


class LookupArgs(BaseModel):
    query: str = Field(min_length=1, max_length=20)


class LookupTool(Tool):
    name = "lookup"
    description = "Look up a test value."
    args_model = LookupArgs

    def __init__(self):
        self.calls = []

    def execute(self, **kwargs) -> str:
        self.calls.append(kwargs)
        return "lookup result"


class CitationLookupTool(LookupTool):
    def execute(self, **kwargs) -> str:
        result = super().execute(**kwargs)
        self.last_citations = [{
            "source": "tinydb/storages.py",
            "excerpt": "class JSONStorage(Storage):",
        }]
        return result


def test_function_calling_executes_valid_tool_and_returns_final_answer(monkeypatch):
    tool = LookupTool()
    harness = AgentHarness(tools=[tool])
    harness._schedule_log = lambda **_: None
    responses = iter([
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [{
                "id": "call-1",
                "type": "function",
                "function": {"name": "lookup", "arguments": '{"query": "TinyDB"}'},
            }],
        },
        {"role": "assistant", "content": "final answer", "tool_calls": []},
    ])
    requests = []

    def fake_call(messages, tools, **kwargs):
        requests.append(messages.copy())
        assert tools == [tool.function_schema()]
        return next(responses)

    monkeypatch.setattr("app.agent.harness.call_llm_with_tools", fake_call)

    assert harness.run("look up TinyDB") == "final answer"
    assert tool.calls == [{"query": "TinyDB"}]
    assert harness.execution_trace == [{
        "step": 1,
        "tool_name": "lookup",
        "arguments": {"query": "TinyDB"},
        "status": "completed",
        "observation": "lookup result",
    }]
    assert requests[1][-1] == {
        "role": "tool", "tool_call_id": "call-1", "content": "lookup result"
    }


def test_function_calling_rejects_invalid_arguments_without_executing_tool(monkeypatch):
    tool = LookupTool()
    harness = AgentHarness(tools=[tool])
    harness._schedule_log = lambda **_: None
    responses = iter([
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [{
                "id": "call-1",
                "type": "function",
                "function": {"name": "lookup", "arguments": '{"query": ""}'},
            }],
        },
        {"role": "assistant", "content": "invalid arguments", "tool_calls": []},
    ])
    requests = []

    def fake_call(messages, tools, **kwargs):
        requests.append(messages.copy())
        return next(responses)

    monkeypatch.setattr("app.agent.harness.call_llm_with_tools", fake_call)

    assert harness.run("look up") == "invalid arguments"
    assert tool.calls == []
    assert harness.execution_trace[0]["status"] == "rejected"
    assert harness.execution_trace[0]["arguments"] is None
    assert '"error"' in requests[1][-1]["content"]


def test_tool_citations_are_added_to_trace_and_final_response(monkeypatch):
    tool = CitationLookupTool()
    harness = AgentHarness(tools=[tool])
    harness._schedule_log = lambda **_: None
    responses = iter([
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [{
                "id": "call-1",
                "type": "function",
                "function": {"name": "lookup", "arguments": '{"query": "TinyDB"}'},
            }],
        },
        {"role": "assistant", "content": "final answer", "tool_calls": []},
    ])
    monkeypatch.setattr(
        "app.agent.harness.call_llm_with_tools",
        lambda messages, tools, **kwargs: next(responses),
    )

    assert harness.run("look up TinyDB") == "final answer"
    assert harness.citations == [{
        "source": "tinydb/storages.py",
        "excerpt": "class JSONStorage(Storage):",
    }]
    assert harness.execution_trace[0]["citations"] == harness.citations


def test_function_calling_rejects_repeated_tool_call(monkeypatch):
    tool = LookupTool()
    harness = AgentHarness(tools=[tool])
    harness._schedule_log = lambda **_: None
    tool_call = {
        "id": "call-1",
        "type": "function",
        "function": {"name": "lookup", "arguments": '{"query": "TinyDB"}'},
    }
    responses = iter([
        {"role": "assistant", "content": "", "tool_calls": [tool_call]},
        {"role": "assistant", "content": "", "tool_calls": [tool_call]},
        {"role": "assistant", "content": "final answer", "tool_calls": []},
    ])

    monkeypatch.setattr(
        "app.agent.harness.call_llm_with_tools",
        lambda messages, tools, **kwargs: next(responses),
    )

    assert harness.run("look up TinyDB") == "final answer"
    assert tool.calls == [{"query": "TinyDB"}]
    assert [item["status"] for item in harness.execution_trace] == ["completed", "rejected"]
    assert "Repeated tool call" in harness.execution_trace[1]["observation"]


def test_max_steps_still_returns_a_bounded_final_answer(monkeypatch):
    tool = LookupTool()
    harness = AgentHarness(tools=[tool])
    harness._schedule_log = lambda **_: None
    responses = iter([
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [{
                "id": "call-1",
                "type": "function",
                "function": {"name": "lookup", "arguments": '{"query": "one"}'},
            }],
        },
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [{
                "id": "call-2",
                "type": "function",
                "function": {"name": "lookup", "arguments": '{"query": "two"}'},
            }],
        },
    ])

    monkeypatch.setattr(
        "app.agent.harness.call_llm_with_tools",
        lambda messages, tools, **kwargs: next(responses),
    )
    monkeypatch.setattr(
        "app.agent.harness.call_llm_with_messages",
        lambda messages, **kwargs: "基于已检索证据的最终答案",
    )

    assert harness.run("look up", max_step=2) == "基于已检索证据的最终答案"
    assert len(tool.calls) == 2


def test_streaming_agent_emits_progress_trace_and_answer_deltas(monkeypatch):
    tool = LookupTool()
    harness = AgentHarness(tools=[tool])
    harness._schedule_log = lambda **_: None
    events = []
    tool_response = {
        "role": "assistant",
        "content": "",
        "tool_calls": [{
            "id": "call-1",
            "type": "function",
            "function": {"name": "lookup", "arguments": '{"query": "TinyDB"}'},
        }],
    }
    responses = iter([
        tool_response,
        {"role": "assistant", "content": "intermediate answer", "tool_calls": []},
    ])

    monkeypatch.setattr(
        "app.agent.harness.call_llm_with_tools",
        lambda messages, tools, **kwargs: next(responses),
    )

    def fake_stream(messages, on_delta, **kwargs):
        on_delta("流式")
        on_delta("答案")
        return "流式答案"

    monkeypatch.setattr("app.agent.harness.call_llm_with_messages_stream", fake_stream)

    answer = harness.run(
        "look up TinyDB",
        emit=lambda event, data: events.append((event, data)),
        stream_final=True,
    )

    assert answer == "流式答案"
    assert tool.calls == [{"query": "TinyDB"}]
    assert [event for event, _ in events] == [
        "status", "status", "trace", "status", "status", "status", "delta", "delta",
    ]


def test_cancelled_agent_does_not_start_an_llm_call(monkeypatch):
    harness = AgentHarness(tools=[LookupTool()])
    cancel_event = Event()
    cancel_event.set()
    monkeypatch.setattr(
        "app.agent.harness.call_llm_with_tools",
        lambda *args, **kwargs: pytest.fail("LLM should not be called after cancellation"),
    )

    with pytest.raises(AgentCancelled):
        harness.run("look up TinyDB", cancel_event=cancel_event)


def test_llm_client_sends_tool_schema_and_preserves_tool_call(monkeypatch):
    request = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "choices": [{"message": {
                    "content": None,
                    "tool_calls": [{
                        "id": "call-1",
                        "type": "function",
                        "function": {"name": "lookup", "arguments": '{"query": "TinyDB"}'},
                    }],
                }}],
            }

    def fake_post(url, json, headers, timeout):
        request.update({"url": url, "body": json, "headers": headers, "timeout": timeout})
        return FakeResponse()

    monkeypatch.setattr(llm.httpx, "post", fake_post)
    schema = LookupTool().function_schema()
    result = llm.call_llm_with_tools(
        [{"role": "user", "content": "look up TinyDB"}],
        [schema],
        max_retries=0,
    )

    assert request["body"]["tools"] == [schema]
    assert request["body"]["tool_choice"] == "auto"
    assert result["content"] is None
    assert result["tool_calls"][0]["function"]["name"] == "lookup"


def test_llm_streaming_client_emits_text_deltas(monkeypatch):
    request = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def iter_lines(self):
            return iter([
                'data: {"choices":[{"delta":{"content":"流式"}}]}',
                'data: {"choices":[{"delta":{"content":"回答"}}]}',
                "data: [DONE]",
            ])

    class FakeStream:
        def __enter__(self):
            return FakeResponse()

        def __exit__(self, *args):
            return None

    def fake_stream(method, url, json, headers, timeout):
        request.update({"method": method, "body": json, "timeout": timeout})
        return FakeStream()

    monkeypatch.setattr(llm.httpx, "stream", fake_stream)
    deltas = []

    answer = llm.call_llm_with_messages_stream(
        [{"role": "user", "content": "hello"}],
        deltas.append,
        timeout_seconds=12,
    )

    assert request["method"] == "POST"
    assert request["body"]["stream"] is True
    assert request["timeout"] == 12
    assert deltas == ["流式", "回答"]
    assert answer == "流式回答"
