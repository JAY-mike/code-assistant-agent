"""Lightweight Agent smoke evaluation without an external judge."""

import asyncio

from app.agent.eval_tasks import EVAL_TASKS
from app.agent.harness import AgentHarness


async def run_eval() -> list[dict]:
    results = []
    for index, task in enumerate(EVAL_TASKS, start=1):
        harness = AgentHarness(session_id=f"agent-eval-{index:02d}")
        answer = await asyncio.to_thread(harness.run, task["question"])
        trace = harness.execution_trace
        results.append({
            "task": task["description"],
            "answer_received": bool(answer) and not answer.startswith("Error:"),
            "tool_call_count": len(trace),
            "rejected_tool_call_count": sum(
                item["status"] == "rejected" for item in trace
            ),
        })

    for result in results:
        print(
            f"{result['task']}: answer={result['answer_received']} "
            f"tools={result['tool_call_count']} rejected={result['rejected_tool_call_count']}"
        )
    return results


if __name__ == "__main__":
    asyncio.run(run_eval())
