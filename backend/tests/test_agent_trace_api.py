"""Chat API trace response tests without a live LLM or database."""

import json
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth import get_current_user
from app.agent.harness import AgentCancelled
from app.routers import agent_router


def test_chat_returns_tool_execution_trace(monkeypatch):
    class FakeHarness:
        def __init__(self, session_id, knowledge_base_id):
            self.session_id = session_id
            self.knowledge_base_id = knowledge_base_id
            self.execution_trace = []
            self.citations = []

        def restore_history(self, history):
            self.history = history

        def run(self, message):
            self.execution_trace = [{
                "step": 1,
                "tool_name": "search",
                "arguments": {"query": "TinyDB storage"},
                "status": "completed",
                "observation": "[storages.py] JSONStorage",
            }]
            return "TinyDB uses JSONStorage."

    async def no_op(*args, **kwargs):
        return None

    app = FastAPI()
    app.include_router(agent_router.router, prefix="/api")
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=7)
    monkeypatch.setattr(agent_router, "AgentHarness", FakeHarness)
    monkeypatch.setattr(agent_router, "get_or_create_conversation", no_op)
    monkeypatch.setattr(agent_router, "load_history", no_op)
    monkeypatch.setattr(agent_router, "save_message", no_op)

    with TestClient(app) as client:
        response = client.post(
            "/api/agent/chat",
            json={
                "message": "How is data stored?",
                "session_id": "trace-session",
                "knowledge_base": "project",
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload == {
        "answer": "TinyDB uses JSONStorage.",
        "session_id": "trace-session",
        "trace": [{
            "step": 1,
            "tool_name": "search",
            "arguments": {"query": "TinyDB storage"},
            "status": "completed",
            "observation": "[storages.py] JSONStorage",
            "citations": [],
        }],
        "citations": [],
        "metrics": payload["metrics"],
    }
    assert payload["metrics"] == {
        "server_e2e_latency_ms": payload["metrics"]["server_e2e_latency_ms"],
        "agent_latency_ms": 0.0,
        "coordinator_llm_latency_ms": 0.0,
        "tool_latency_ms": 0.0,
        "coordinator_llm_call_count": 0,
        "tool_call_count": 0,
        "time_to_first_token_ms": None,
    }
    assert payload["metrics"]["server_e2e_latency_ms"] >= 0


def test_stream_chat_returns_sse_events(monkeypatch):
    class FakeHarness:
        def __init__(self, session_id, knowledge_base_id):
            self.execution_trace = []
            self.citations = []

        def restore_history(self, history):
            self.history = history

        def run(self, message, emit=None, stream_final=False, **kwargs):
            assert stream_final is True
            return fake_run_stream(self, message, emit)

    async def no_op(*args, **kwargs):
        return None

    def fake_run_stream(harness, message, emit):
        emit("status", {"message": "正在分析问题..."})
        harness.execution_trace = [{
            "step": 1,
            "tool_name": "search",
            "arguments": {"query": "TinyDB storage"},
            "status": "completed",
            "observation": "[storages.py] JSONStorage",
        }]
        emit("trace", {"trace": harness.execution_trace[0]})
        emit("delta", {"text": "TinyDB "})
        emit("delta", {"text": "uses JSONStorage."})
        return "TinyDB uses JSONStorage."

    app = FastAPI()
    app.include_router(agent_router.router, prefix="/api")
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=7)
    monkeypatch.setattr(agent_router, "AgentHarness", FakeHarness)
    monkeypatch.setattr(agent_router, "get_or_create_conversation", no_op)
    monkeypatch.setattr(agent_router, "load_history", no_op)
    monkeypatch.setattr(agent_router, "save_message", no_op)

    with TestClient(app) as client:
        response = client.post(
            "/api/agent/chat/stream",
            json={
                "message": "How is data stored?",
                "session_id": "trace-session",
                "knowledge_base": "project",
            },
        )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert 'event: status\ndata: {"message": "正在分析问题..."}' in response.text
    assert 'event: delta\ndata: {"text": "TinyDB "}' in response.text
    done_data = response.text.split("event: done\ndata: ", 1)[1].split("\n\n", 1)[0]
    done = json.loads(done_data)
    assert done["session_id"] == "trace-session"
    assert done["citations"] == []
    assert done["metrics"]["server_e2e_latency_ms"] >= 0
    assert done["metrics"]["time_to_first_token_ms"] is not None


def test_cancelled_stream_does_not_persist_messages(monkeypatch):
    class FakeHarness:
        def __init__(self, session_id, knowledge_base_id):
            self.execution_trace = []

        def restore_history(self, history):
            self.history = history

        def run(self, message, **kwargs):
            raise AgentCancelled("cancelled")

    saved_messages = []

    async def no_op(*args, **kwargs):
        return None

    async def save(*args):
        saved_messages.append(args)

    app = FastAPI()
    app.include_router(agent_router.router, prefix="/api")
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=7)
    monkeypatch.setattr(agent_router, "AgentHarness", FakeHarness)
    monkeypatch.setattr(agent_router, "get_or_create_conversation", no_op)
    monkeypatch.setattr(agent_router, "load_history", no_op)
    monkeypatch.setattr(agent_router, "save_message", save)

    with TestClient(app) as client:
        response = client.post(
            "/api/agent/chat/stream",
            json={
                "message": "How is data stored?",
                "session_id": "trace-session",
                "knowledge_base": "project",
            },
        )

    assert response.status_code == 200
    assert 'event: cancelled\ndata: {"message": "生成已取消。"}' in response.text
    assert saved_messages == []
