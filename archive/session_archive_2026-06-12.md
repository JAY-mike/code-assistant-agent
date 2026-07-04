# 2026-06-12 会话归档

> 保存时间：2026-06-17
> 目的：上下文压缩后重新接续会话时使用

---

## 一、当前项目进度

**Week 1 进行中。** Day 1-2 已完成，Day 3 待续。

### 已完成模块
- 项目骨架 + Git 初始化（2 个 commit）
- config.py + .env 配置管理
- database.py + 异步 SQLAlchemy 引擎
- Conversation / Message / Feedback ORM 模型
- docker-compose.yml（MySQL 8.0 + Redis 7）
- main.py（FastAPI + 自动建表 + /health）
- chunker.py（多策略分块：recursive / semantic / token）
- dense_retriever.py（Chroma 检索封装）

### 下一步（Week 1 Day 3）
- 修改 code_indexer.py → 简化为主流程编排器
- config.py 加分块策略配置项 `CHUNK_STRATEGY`

---

## 二、8 周路线图（高亮版）

```
Week 1 ██░ chunker + dense_retriever + index_versions + Redis 缓存    ← 当前
Week 2 ██░ BM25 + RRF + retrieval_logs
Week 3 ██░ 查询改写 + cross-encoder 重排
Week 4 ██░ 评估指标 + 消融实验
Week 5 ██░ Agent Harness + ReAct + 三个工具 + 决策日志
Week 6 ██░ API + JWT + 文件上传 + Streamlit + 反馈 + 限流
Week 7 ██░ Docker + Railway + CI/CD + 并发
Week 8 ██░ Demo + README + 面试话术
```

---

## 三、项目最终规划

### RAG — 深度：中
多策略分块 + Dense/Sparse 混合检索 + HyDE 改写 + RRF 融合 + cross-encoder 重排 + 消融实验。

### Agent — 深度：中（预留 LangGraph 接口）
ReAct + 真实 LLM + Harness（注册/执行/评测）+ 多轮记忆 + 可视化 + 限流 + 成功率评估。

### 文件上传 — 深度：中
用户上传 .py/.js/.java/.md/.pdf/.png/.jpg → 自动检测类型 + PDF 提取 + OCR → 复用 chunker → 独立 Chroma collection → 合并检索。

### JWT 鉴权 — 深度：中
注册 + 登录 + Refresh Token + 路由分级保护 + Redis 黑名单登出 + bcrypt。

### 并发 — 深度：轻~中（时间充裕时加）
连接池 + 限流 + 请求监控。

### MySQL / Redis / 前端 / Docker / CI/CD — 轻~中

---

## 四、技术选型

| 决策 | 选择 |
|---|---|
| Embedding | all-MiniLM-L6-v2 |
| BM25 | rank_bm25 库（不手写） |
| Reranker | bge-reranker-v2-m3（cross-encoder） |
| 融合算法 | RRF（公式 1/(k+rank)） |
| 查询改写 | HyDE |
| LLM（开发） | Ollama + qwen2:7b（已安装） |
| LLM（生产） | DeepSeek API |
| 前端 | Streamlit |
| 部署 | Docker → Railway/Render |
| 鉴权 | python-jose + passlib(bcrypt) + Redis 黑名单 |
| PDF | PyMuPDF |
| OCR | Tesseract |
| 代码索引目标 | TinyDB（msiemens/tinydb） ~12 文件 |

---

## 五、面试题文档

`data/interview_prep.md` — 11 部分，约 120 道题：

1. 项目拷打 Q&A
2. RAG 八股（含 BM25 公式、RRF 原理）
3. Agent 八股（含 Harness、评测）
4. LLM 八股（含 Token、SFT/RLHF）
5. LangChain / LangGraph 八股
6. Python 后端八股
7. MySQL 八股
8. Redis 八股
9. Docker 部署八股
10. 场景题
11. 文件上传 & 多模态处理

---

## 六、用户档案

- 大二学生
- 已学：MySQL、Redis、FastAPI、了解 LangChain 和 RAG
- 每天能投入 2-3 小时
- 找 AI 大模型应用开发 / Agent 方向实习
- 已安装 Ollama + qwen2:7b
- Python 3.12+
- Windows 环境
- 偏好：我给完整代码，他一次性创建，我逐段讲解
