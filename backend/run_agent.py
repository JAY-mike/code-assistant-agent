# """Agent 批量评测：语义相似度自动打分"""

# import asyncio
# from app.agent.harness import AgentHarness
# from app.agent.eval_tasks import EVAL_TASKS
# from app.rag.dense_retriever import DenseRetriever
# from app.database import engine, Base


# def semantic_score(answer: str, reference: str) -> float:
#     """用 embedding 计算回答和参考要点的语义相似度（0-1）"""
#     retriever = DenseRetriever()
#     emb = retriever.embeddings
#     vec_answer = emb.embed_query(answer)
#     vec_ref = emb.embed_query(reference)

#     dot = sum(a * b for a, b in zip(vec_answer, vec_ref))
#     norm_a = sum(a * a for a in vec_answer) ** 0.5
#     norm_r = sum(b * b for b in vec_ref) ** 0.5
#     return dot / (norm_a * norm_r) if norm_a > 0 and norm_r > 0 else 0.0


# async def run_eval():
#     async with engine.begin() as conn:
#         await conn.run_sync(Base.metadata.create_all)

#     results = []
#     total_score = 0

#     for i, task in enumerate(EVAL_TASKS):
#         session_id = f"eval_task_{i+1:02d}"
#         harness = AgentHarness(session_id=session_id)

#         question = task["question"]
#         desc = task["description"]
#         print(f"\n[{i+1}/{len(EVAL_TASKS)}] {desc}")
#         print(f"  问: {question[:40]}...")

#         answer = harness.run(question)
#         await asyncio.sleep(0.3)

#         sim = semantic_score(answer, task["reference"])
#         total_score += sim

#         bar = "█" * int(sim * 10) + "░" * (10 - int(sim * 10))
#         print(f"  相似度: {sim:.2f} {bar}")
#         results.append({"task": desc, "similarity": sim})

#     total = len(EVAL_TASKS)
#     avg = total_score / total
#     print(f"\n{'='*50}")
#     print(f"评测完成: 平均相似度 {avg:.2f} (满分 1.0)")
#     print(f"{'='*50}")
#     for r in results:
#         bar = "█" * int(r["similarity"] * 10) + "░" * (10 - int(r["similarity"] * 10))
#         print(f"  {bar} {r['task']} ({r['similarity']:.2f})")
#     print(f"{'='*50}")

#     await engine.dispose()


# if __name__ == "__main__":
#     asyncio.run(run_eval())



# """多轮对话测试"""

# import asyncio
# from app.agent.harness import AgentHarness
# from app.database import engine, Base
# from app.models.agent_log import AgentLog


# async def main():
#     async with engine.begin() as conn:
#         await conn.run_sync(Base.metadata.create_all)

#     harness = AgentHarness(session_id="multi_turn_test")

#     # 第一轮
#     q1 = "TinyDB 怎么把数据存到磁盘上的？"
#     print(f"\n[Round 1] {q1}")
#     a1 = harness.run(q1)
#     print(f"回答: {a1[:200]}...")

#     # 第二轮（依赖第一轮的上下文）
#     q2 = "那它查询数据又是怎么实现的？"
#     print(f"\n[Round 2] {q2}")
#     a2 = harness.run(q2)
#     print(f"回答: {a2[:200]}...")

#     await asyncio.sleep(0.5)
#     await engine.dispose()


# if __name__ == "__main__":
#     asyncio.run(main())


from app.config import settings
from app.auth import SECRET_KEY, decode_token
print("SECRET_KEY:", SECRET_KEY)
print("settings.JWT_SECRET:", settings.JWT_SECRET)

# 用你刚才拿到的 token 测试
token = "粘贴你的access_token"
try:
    print(decode_token(token))
except Exception as e:
    print("decode error:", e)