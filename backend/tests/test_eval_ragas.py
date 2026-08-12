"""Offline contract tests for the optional RAGAS evaluation script."""

import pytest

from scripts import eval_ragas


def test_build_samples_uses_question_context_answer_and_reference(monkeypatch):
    monkeypatch.setattr(
        eval_ragas,
        "retrieve_contexts",
        lambda question, knowledge_base_id: [f"context for {knowledge_base_id}:{question}"],
    )
    monkeypatch.setattr(
        eval_ragas,
        "answer_with_context",
        lambda question, contexts, knowledge_base_id: f"answer for {knowledge_base_id}:{question}",
    )

    samples = eval_ragas.build_samples()

    assert len(samples) == len(eval_ragas.EVAL_TASKS)
    assert set(samples[0]) == {"question", "contexts", "answer", "ground_truth"}
    assert samples[0]["contexts"]
    assert samples[0]["ground_truth"] == eval_ragas.EVAL_TASKS[0]["reference"]


def test_project_eval_set_is_grounded_and_builds_ragas_samples(monkeypatch):
    tasks = eval_ragas.load_eval_tasks("project")

    assert len(tasks) == 34
    assert all(task["evidence_sources"] for task in tasks)
    assert all("data/eval" not in source for task in tasks for source in task["evidence_sources"])

    monkeypatch.setattr(
        eval_ragas,
        "retrieve_contexts",
        lambda question, knowledge_base_id: [f"context for {knowledge_base_id}:{question}"],
    )
    monkeypatch.setattr(
        eval_ragas,
        "answer_with_context",
        lambda question, contexts, knowledge_base_id: f"answer for {knowledge_base_id}:{question}",
    )

    samples = eval_ragas.build_samples("project")

    assert len(samples) == len(tasks)
    assert set(samples[0]) == {"question", "contexts", "answer", "ground_truth"}


def test_judge_base_url_requires_openai_compatible_endpoint():
    assert eval_ragas._judge_base_url("https://api.deepseek.com/v1/chat/completions") == (
        "https://api.deepseek.com/v1"
    )
    with pytest.raises(RuntimeError, match="OpenAI-compatible"):
        eval_ragas._judge_base_url("http://localhost:11434/api/chat")
