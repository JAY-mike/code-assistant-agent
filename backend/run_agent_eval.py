"""Agent 批量评测：逐个跑测试任务，统计成功率"""

import asyncio
from app.agent.harness import AgentHarness
from app.agent.eval_tasks import EVAL_TASKS
from app.database import engine, Base
from app.models.agent_log import AgentLog


def evaluate_answer(answer: str, expected_keywords: list[str]) -> bool:
    """检查回答是否包含所有期望关键词"""
    answer_lower = answer.lower()
    for kw in expected_keywords:
        if kw.lower() not in answer_lower:
            return False
    return True


async def run_eval():
    # 确保表存在
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    results = []
    passed = 0

    for i, task in enumerate(EVAL_TASKS):
        session_id = f"eval_task_{i+1:02d}"
        harness = AgentHarness(session_id=session_id)

        question = task["question"]
        print(f"\n[{i+1}/{len(EVAL_TASKS)}] {task['description']}")
        print(f"  问: {question[:40]}...")

        answer = harness.run(question)

        # 等日志写完
        await asyncio.sleep(0.5)

        # 从数据库查实际用过的工具
        async with engine.begin() as conn:
            from sqlalchemy import text
            rows = await conn.execute(
                text("SELECT DISTINCT action_name FROM agent_logs WHERE session_id = :sid"),
                {"sid": session_id},
            )
            used_tools = [row[0] for row in rows if row[0] != "answer"]

        keyword_ok = evaluate_answer(answer, task["expected_keywords"])
        tool_ok = any(t in used_tools for t in task["expected_tool_usage"])

        score = "PASS" if (keyword_ok and tool_ok) else "FAIL"
        if score == "PASS":
            passed += 1

        print(f"  关键词: {'✅' if keyword_ok else '❌'} 工具: {'✅' if tool_ok else '❌'}")
        print(f"  结果: {score}")

        results.append({
            "task": task["description"],
            "keyword_pass": keyword_ok,
            "tool_pass": tool_ok,
            "score": score,
        })

    # 总结
    total = len(EVAL_TASKS)
    print(f"\n{'='*50}")
    print(f"评测完成: {passed}/{total} 通过 ({passed/total*100:.1f}%)")
    print(f"{'='*50}")
    for r in results:
        print(f"  {'✅' if r['score']=='PASS' else '❌'} {r['task']}")
    print(f"{'='*50}")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(run_eval())