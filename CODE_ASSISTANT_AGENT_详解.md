# Code Assistant Agent 项目全源码精讲

> 一个基于 RAG 的代码问答与 Agent 系统，以 TinyDB 开源项目 + 项目自身源码为双知识库。
> 本教程按「由地基到屋顶」的顺序，对项目中的核心实现、部署配置与主要测试文件进行详细讲解。

---

## 阅读指南

### 本教程是什么

这份文档把 `code-assistant-agent` 项目（FastAPI + RAG + Tool-Calling Agent + Streamlit + Docker）的**核心实现、部署配置与主要测试文件**讲一遍（不含空包初始化文件、`backend` 根目录的临时调试脚本等）。每一章的结构统一为：

1. **完整代码**：先把文件原样贴出来，你可以对着看。
2. **这段代码解决什么问题**：先讲设计意图，再讲实现。
3. **关键代码逐句拆解**：挑出值得细品的行，讲清楚"为什么这么写"。
4. **面试答题要点**：面试官可能怎么问，你该怎么答。

### 推荐的阅读方法

- **顺序阅读**：第 1 层到第 8 层是按依赖关系排的，先讲地基、再讲业务。跳过前面的文件，后面的会出现看不懂的引用。
- **对照源码**：建议同时打开项目目录，找到对应的文件，边看边读。
- **动手验证**：每章结尾的「动手做」建议，跑一遍比只看代码理解深得多。
- **随时查**：这份文档里保留了完整代码块，可脱离项目单独阅读。

### 项目文件总览

先给你一张"地图"，后面每一层都会展开：

```
code-assistant-agent/
├── backend/
│   ├── app/
│   │   ├── config.py              # 【第1层】总配置（含 PROJECT_SOURCE_PATH）
│   │   ├── logger.py              # 【第1层】统一日志
│   │   ├── database.py            # 【第1层】异步数据库引擎 + 依赖注入
│   │   ├── auth.py                # 【第3层】JWT 鉴权 + bcrypt + Redis 黑名单
│   │   ├── middleware.py          # 【第3层】Redis 滑动窗口限流（可注入 redis_client）
│   │   ├── clients.py             # 【第3层】共享 Redis 客户端（进程级单例）
│   │   ├── models/                # 【第2层】9 张表的 ORM 模型
│   │   │   ├── user.py
│   │   │   ├── conversation.py
│   │   │   ├── agent_log.py
│   │   │   ├── retrieval_log.py
│   │   │   ├── query_rewrite.py
│   │   │   ├── evaluation_run.py
│   │   │   ├── index_version.py
│   │   │   ├── feedback.py
│   │   │   └── __init__.py
│   │   ├── rag/                   # 【第4层】RAG 检索管线
│   │   │   ├── chunker.py
│   │   │   ├── knowledge_bases.py # 多知识库静态定义（tinydb / project）
│   │   │   ├── dense_retriever.py # 稠密检索（按 collection 隔离 + 清缓存）
│   │   │   ├── sparse_retriever.py
│   │   │   ├── fusion.py
│   │   │   ├── query_rewriter.py
│   │   │   ├── reranker.py
│   │   │   ├── code_indexer.py    # 离线索引（多知识库重建）
│   │   │   ├── user_upload.py     # 用户上传（独立 user_uploads collection）
│   │   │   ├── test_set.py
│   │   │   └── evaluation.py
│   │   ├── agent/                 # 【第5层】Tool-Calling Agent
│   │   │   ├── llm.py             # LLM 调用（含 tool-calling 接口）
│   │   │   ├── tool_base.py       # 工具基类（Pydantic args_model + function_schema）
│   │   │   ├── prompt.py          # 系统提示词（按知识库动态生成）
│   │   │   ├── tools.py           # 三个工具（绑定知识库）
│   │   │   ├── harness.py         # Agent 循环（原生 tool-calling + 重复调用检测）
│   │   │   └── eval_tasks.py      # Agent 评测任务集（预留）
│   │   ├── services/              # 【第6层】业务服务层
│   │   │   └── conversation_service.py
│   │   ├── routers/               # 【第7层】API 路由层
│   │   │   ├── auth_router.py
│   │   │   ├── agent_router.py    # 多知识库 + SSE 流式 + 执行轨迹 + 引用 + 性能指标
│   │   │   ├── search_router.py   # 多知识库 + 真实 latency + /search/source 源码查看
│   │   │   └── upload_router.py
│   │   └── main.py                # 【第8层】应用入口
│   ├── scripts/                   # 辅助脚本
│   │   └── eval_ragas.py          # 可选 RAGAS 评估（Judge LLM 打分）
│   ├── data/
│   │   └── eval/                  # project 知识库评测题集（JSON）
│   ├── tests/                     # 【第8.6层】单元测试与集成测试
│   │   ├── conftest.py            # 测试环境配置（连测试库、跳过密钥校验）
│   │   ├── test_auth.py           # 密码哈希单元测试
│   │   ├── test_auth_api.py       # 鉴权 API 集成测试
│   │   ├── test_fusion.py         # RRF 融合单元测试
│   │   ├── test_metrics.py        # 评估指标单元测试
│   │   ├── test_rate_limit.py     # 限流中间件测试（FakeRedis）
│   │   ├── test_user_upload.py    # 上传隔离单元测试（FakeRetriever）
│   │   ├── test_function_calling.py  # Agent 工具调用测试（无 LLM）
│   │   ├── test_agent_trace_api.py  # Agent 执行轨迹 API 测试
│   │   ├── test_eval_ragas.py     # RAGAS 评估测试
│   │   └── test_knowledge_bases.py  # 多知识库定义测试
│   └── Dockerfile                 # 【第8层】后端镜像
├── frontend/
│   ├── streamlit_app.py           # 【第8层】Streamlit 前端
│   └── Dockerfile                 # 【第8层】前端镜像
├── docker-compose.yml             # 【第8层】一键部署
├── .github/workflows/ci.yml       # 【第8层】CI
├── docs/                          # 项目文档（演示脚本等）
├── .env.example                   # 环境变量模板
└── README.md                      # 项目说明
```

### 目录

- [第 0 章 项目整体架构](#第-0-章-项目整体架构)
- [第 1 层 地基：配置 / 日志 / 数据库](#第-1-层-地基配置--日志--数据库)
  - [1.1 config.py](#11-configpy--总控制台)
  - [1.2 logger.py](#12-loggerpy--监控探头)
  - [1.3 database.py](#13-databasepy--管道系统)
- [第 2 层 数据模型：9 张表的仓库](#第-2-层-数据模型9-张表的仓库)
  - [2.1 models/__init__.py](#21-models__init__py--模型的汇总清单)
  - [2.2 user.py](#22-userpy--用户表)
  - [2.3 conversation.py](#23-conversationpy--会话与消息表)
  - [2.4 agent_log.py](#24-agent_logpy--agent-决策日志)
  - [2.5 retrieval_log.py](#25-retrieval_logpy--检索日志)
  - [2.6 query_rewrite.py](#26-query_rewritepy--查询改写记录)
  - [2.7 evaluation_run.py](#27-evaluation_runpy--评估运行记录)
  - [2.8 index_version.py](#28-index_versionpy--索引版本记录)
  - [2.9 feedback.py](#29-feedbackpy--用户反馈)
- [第 3 层 安全：鉴权与限流](#第-3-层-安全鉴权与限流)
  - [3.1 auth.py](#31-authpy--jwt-鉴权全家桶)
  - [3.2 middleware.py](#32-middlewarepy--redis-滑动窗口限流)
  - [3.3 clients.py](#33-clientspy--共享客户端进程级单例)
- [第 4 层 RAG 检索管线](#第-4-层-rag-检索管线)
  - [4.1 chunker.py](#41-chunkerpy--代码分块器)
  - [4.2 knowledge_bases.py](#42-knowledge_basespy--多知识库定义)
  - [4.3 dense_retriever.py](#43-dense_retrieverpy--稠密向量检索)
  - [4.4 sparse_retriever.py](#44-sparse_retrieverpy--bm25-稀疏检索)
  - [4.5 fusion.py](#45-fusionpy--rrf-结果融合)
  - [4.6 query_rewriter.py](#46-query_rewriterpy--hyde-查询改写)
  - [4.7 reranker.py](#47-rerankerpy--cross-encoder-重排)
  - [4.8 code_indexer.py](#48-code_indexerpy--离线索引编排器)
  - [4.9 user_upload.py](#49-user_uploadpy--用户上传隔离检索)
  - [4.10 test_set.py](#410-test_setpy--评测测试集)
  - [4.11 evaluation.py](#411-evaluationpy--评估引擎与消融实验)
  - [4.12 scripts/eval_ragas.py](#412-scriptseval_ragaspy--端到端-ragas-评估脚本)
- [第 5 层 Agent：让模型自己决策](#第-5-层-agent让模型自己决策)
  - [5.1 llm.py](#51-llmpy--llm-调用封装)
  - [5.2 tool_base.py](#52-tool_basepy--工具抽象基类)
  - [5.3 prompt.py](#53-promptpy--系统提示词)
  - [5.4 tools.py](#54-toolspy--三个-rag-工具)
  - [5.5 harness.py](#55-harnesspy--tool-calling-循环引擎全项目核心)
  - [5.6 eval_tasks.py](#56-eval_taskspy--agent-评测任务集预留)
- [第 6 层 服务层](#第-6-层-服务层)
  - [6.1 conversation_service.py](#61-conversation_servicepy--会话持久化服务)
- [第 7 层 API 路由层](#第-7-层-api-路由层)
  - [7.1 auth_router.py](#71-auth_routerpy--认证接口)
  - [7.2 agent_router.py](#72-agent_routerpy--agent-对话接口)
  - [7.3 search_router.py](#73-search_routerpy--代码检索接口)
  - [7.4 upload_router.py](#74-upload_routerpy--文件上传接口)
- [第 8 层 入口与部署](#第-8-层-入口与部署)
  - [8.1 main.py](#81-mainpy--应用入口组装)
  - [8.2 streamlit_app.py](#82-streamlit_apppy--streamlit-前端)
  - [8.3 docker-compose.yml](#83-docker-composeyml--一键部署)
  - [8.4 Dockerfile](#84-dockerfile--后端与前端镜像)
  - [8.5 ci.yml](#85-ciyml--github-actions-持续集成)
  - [8.6 tests/ — 单元测试与集成测试](#86-tests--单元测试与集成测试)
- [第 9 章 全链路数据流总结](#第-9-章-全链路数据流总结)
- [第 10 章 潜在改进建议](#第-10-章-潜在改进建议)
- [附录 A 环境变量参考](#附录-a-环境变量参考)

---

---

# 第 0 章 项目整体架构

## 0.1 这个项目是什么

一句话定位：**这是一个"你问问题，AI 去代码库里翻代码、然后回答你"的系统。**

它维护**两个公开代码知识库**，并提供三种能力：

| 能力 | 说明 | 对应的入口 |
|------|------|-----------|
| **代码检索** | 输入一个问题，返回最相关的代码片段 | `/api/search` |
| **AI 问答** | Agent 自主决定搜什么、怎么搜，最终给出中文回答 | `/api/agent/chat` |
| **测试生成 / 代码解释** | Agent 检索到代码后，让 LLM 解释它或给它写单元测试 | Agent 的 `explain` / `testgen` 工具 |

两个知识库（`knowledge_bases.py` 定义）：
- **tinydb**：TinyDB 开源项目（代码配置中的默认值）。**注意**：需要 `backend/data/target_repo` 下有 TinyDB 源码才能构建索引；当前本机可能缺失该目录（重建会返回 `skipped`），复现 TinyDB 实验前需先恢复对应源码版本。
- **project**：当前 Code Assistant Agent 项目自身源码（当前**真正可构建、可演示**的主线知识库，无需额外源码）。

每个知识库拥有独立的 Chroma collection 和 BM25 索引，互不混合。前端是一个 Streamlit 页面（对话 / 检索 / 上传三个 Tab），后端是 FastAPI。

## 0.2 用一句话形容它的核心价值

它不是一个"玩具 demo"，而是一套**组件完整、工程化齐备、带评估数据**的 AI 应用：

- **RAG 管线完整**：HyDE 查询改写 → 双路召回（稠密 + 稀疏）→ RRF 融合 → cross-encoder 重排，每一步都有对应代码。
- **Agent 走原生 tool-calling**：通过 OpenAI 兼容的 `tools` 参数让 LLM 自主决定调哪个工具，Pydantic 校验参数、重复调用检测、执行轨迹落库。
- **工程化到位**：JWT 鉴权、Redis 滑动窗口限流、数据隔离（系统 / 用户上传分 collection）、多知识库、CI、Docker、可观测日志。
- **有评估**：20 条测试集 + 5 组消融实验，结论是"组件要按领域验证，不能无脑叠加"。

## 0.3 架构总览（用比喻理解）

把整个系统想象成一座**「图书馆 + 咨询台」**：

```
┌─────────────────────────────────────────────────────────────┐
│  你（Streamlit 前端）                                        │
│     │ 携带 JWT 令牌                                          │
│     ▼                                                       │
│  FastAPI 入口 ──► 鉴权（你是谁？）──► 限流（别刷太快）──► 路由分发  │
│     │                                                       │
│     ├──► /api/auth/*    注册 / 登录 / 刷新 / 登出            │
│     ├──► /api/agent/chat    Agent 对话（普通 + SSE 流式）    │
│     ├──► /api/search       直接检索（不走 Agent）            │
│     ├──► /api/search/source  查看引用的完整源码              │
│     └──► /api/upload       上传你自己的代码，索引后也能搜     │
└─────────────────────────────────────────────────────────────┘
```

图书馆有**藏书区**（离线建好的索引）、**检索台**（RAG 管线）、**咨询员**（Agent）。你既可以自己去检索台查（`/api/search`），也可以让咨询员帮你查并总结（`/api/agent/chat`）。咨询员自己也会去检索台查——所以 **Agent 和 RAG 是上下层关系**：RAG 是能力，Agent 是决策者。

## 0.4 核心业务链路：RAG 检索管线

这是项目技术含量最高的部分，也是后面第 4 层要展开的：

```
你的问题
   │
   ▼
（可选：指定知识库 tinydb / project）
   │
   ▼
HyDE 查询改写（可选）——让 LLM 把问题"翻译"成假设代码，再去检索
   │
   ▼
双路召回 ──► 稠密检索 Chroma（all-MiniLM-L6-v2，语义相似）
   │     └──► 稀疏检索 BM25（关键词匹配）
   ▼
RRF 结果融合（Reciprocal Rank Fusion，按排名加权合并两路）
   │
   ▼
Cross-encoder 重排（可选）——把查询和文档拼一起精排，取 top-3
   │
   ▼
top-k 代码片段（带 source 文件路径）
```

**为什么需要双路？** 稠密检索懂语义（"存数据"能匹配到 `storages.py`），但可能漏掉关键词（对 `JSONStorage` 这种专有名词不敏感）；BM25 精确匹配关键词，但不懂同义词。两路互补，融合后更稳。

**为什么融合用 RRF 而不是加权平均？** 因为两路分数的"度量衡"完全不同（一个是向量余弦距离，一个是词频统计），直接相加没有意义。RRF 只看**排名**不看分数，天然规避了分数不可比的问题。

## 0.5 Agent 的 Tool-Calling 循环

Agent 层是项目另一个亮点。它通过 **OpenAI 兼容的原生 tool-calling** 让 LLM 自己决定"要不要查、查什么、查完怎么答"，循环最多 `AGENT_MAX_STEPS`（默认 4）步，且有总时长预算（`AGENT_MAX_DURATION_SECONDS`）：

```
① 系统提示词 + 历史 + 用户问题组装成 messages
② 调 call_llm_with_tools（携带工具 schema）→ LLM 返回结构化消息
③ 有 tool_calls → 逐个校验参数（Pydantic）→ 执行工具 → 把 tool 消息注入 → 回到②
④ 无 tool_calls → 认为 content 是最终答案 → 返回
⑤ 超过步数/时长预算 → 基于已有证据优雅降级回答
```

**相比早期手写 ReAct（LLM 输出 Action JSON + 括号深度解析），现在改用原生 tool-calling**：LLM 通过 `tools` 参数原生返回结构化的 `tool_calls`，不再需要自己从文本里解析 JSON；参数用 Pydantic `args_model` 校验，还有重复工具调用检测。后面第 5 层会详细展开。

## 0.6 数据存哪、各司其职

| 存储 | 存什么 | 谁在写 / 谁在读 |
|------|--------|----------------|
| **MySQL 8.0** | 用户、会话、消息、Agent 决策日志、检索日志、评估记录 | ORM 模型（第 2 层）+ 服务层 |
| **Redis 7** | 检索结果缓存、BM25 索引备份、token 黑名单、限流 ZSET | 检索器 / 鉴权 / 中间件 |
| **Chroma**（本地文件） | 稠密向量索引，按 collection 隔离：`system_code` / `project_code` / `user_uploads` | `dense_retriever.py` |
| **文件系统** | `.env` 配置、`data/target_repo`（TinyDB 源码）、`data/chroma`（向量库）、`data/eval`（评测题集） | config / code_indexer |

**关键设计——collection 隔离**：三个 Chroma collection 互不干扰，重建系统索引（`system_code` / `project_code`）不会触碰用户上传的 `user_uploads`。这是数据隔离的物理基础。

## 0.7 技术栈总表

| 层 | 技术 | 关键点 |
|----|------|--------|
| 后端框架 | FastAPI（异步） | asyncio 并发、依赖注入、中间件 |
| ORM / 数据库 | SQLAlchemy 2.0 + aiomysql、MySQL 8.0 | 异步会话、声明式模型 |
| 缓存 / 限流 | Redis 7 | 检索缓存、滑动窗口限流、token 黑名单 |
| 向量库 | Chroma | 本地持久化，多 collection 隔离 |
| Embedding | sentence-transformers/all-MiniLM-L6-v2 | 稠密检索向量化 |
| 检索 | 混合检索（Dense + BM25） | 双路召回 |
| 融合 | RRF | `1/(k+rank)` 无权重融合 |
| 改写 | HyDE | LLM 生成假设文档再检索 |
| 重排 | cross-encoder（ms-marco） | 对 top-N 精排 |
| Agent | 原生 tool-calling | OpenAI 兼容 tools 参数 + Pydantic 参数校验 |
| LLM | DeepSeek API / Ollama | 配置可切换 |
| 前端 | Streamlit | 对话 / 检索 / 上传三 Tab，支持多知识库 |
| 部署 | Docker Compose、GitHub Actions | 一键启动 + CI |

## 0.8 层与层的依赖关系

第 1 层 → 第 2 层 → 第 3 层 → 第 4 层 → 第 5 层 → 第 6 层 → 第 7 层 → 第 8 层

**依赖方向**（谁引用谁）：

- **第 1 层（config / logger / database）**：被所有其他层引用，是地基。
- **第 2 层（models）**：被服务层、路由层、RAG 层引用，是"货架"。
- **第 3 层（auth / middleware）**：被路由层引用，保护整个 API。
- **第 4 层（RAG）**：被 Agent 工具和检索路由引用。
- **第 5 层（Agent）**：调用第 4 层的检索能力 + 第 1 层的 LLM。
- **第 6 层（service）**：被第 7 层路由引用。
- **第 7 层（routers）**：被 main.py 挂载，暴露 API。
- **第 8 层（main / 前端 / 部署 / CI）**：组装一切。

**所以阅读顺序是"由地基到屋顶"**：先懂配置和数据库，再懂数据长什么样，再懂安全，再进入业务核心（RAG 和 Agent），最后看 API 如何暴露、系统如何部署。

---

# 第 1 层 地基：配置 / 日志 / 数据库

学一个项目就像盖一栋楼。第 1 层是**地基**：

- `config.py` —— 决定这栋楼连哪些水电（数据库、Redis、LLM 配置）
- `logger.py` —— 楼里的监控探头（统一日志）
- `database.py` —— 楼里最主要的管道系统（异步数据库连接 + 依赖注入）

不先看懂它们，后面每个文件都会出现你看不懂的引用（`from app.config import settings`、`from app.logger import log`、`Depends(get_db)`）。

---

## 1.1 config.py — 总控制台

### 完整代码

```python
import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
    )

    # App
    APP_NAME: str = "Code Assistant Agent"
    DEBUG: bool = True

    # MySQL
    MYSQL_HOST: str = "localhost"
    MYSQL_PORT: int = 3306
    MYSQL_USER: str = "root"
    MYSQL_PASSWORD: str = "123456"
    MYSQL_DATABASE: str = "code_assistant"

    # Redis
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_CACHE_TTL: int = 300  # 检索缓存过期时间（秒），默认 5 分钟

    # Chroma
    CHROMA_PERSIST_DIR: str = "./data/chroma"

    # 目标代码仓库路径
    REPO_PATH: str = "./data/target_repo"
    # 当前项目源码路径；Docker 环境通过 Compose 挂载为只读目录
    PROJECT_SOURCE_PATH: str = "."

    # Embedding 模型
    # EMBEDDING_MODEL: str = "BAAI/bge-small-zh-v1.5"
    EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"
    EMBEDDING_DEVICE: str = "cpu"

    # 分块策略
    CHUNK_STRATEGY: str = "recursive"  # recursive / semantic / token
    CHUNK_SIZE: int = 500
    CHUNK_OVERLAP: int = 50

    # LLM
    # LLM_API_ENDPOINT: str = "http://localhost:11434/api/chat"  # Ollama
    LLM_API_ENDPOINT: str = "https://api.deepseek.com/v1/chat/completions"
    LLM_MODEL: str = "deepseek-v4-flash"
    LLM_API_KEY: str = ""
    # Agent 受控执行预算：每次用户请求在有限时间内返回。
    AGENT_MAX_STEPS: int = 4
    AGENT_MAX_DURATION_SECONDS: float = 75.0
    AGENT_LLM_TIMEOUT_SECONDS: float = 15.0
    AGENT_LLM_MAX_RETRIES: int = 0
    AGENT_TOOL_LLM_TIMEOUT_SECONDS: float = 12.0
    AGENT_REQUEST_TIMEOUT_SECONDS: float = 80.0
    # LLM_MODEL: str = "gemma:7b"
    # JWT
    JWT_SECRET: str = ""  # 从 .env 读取，禁止硬编码

    def _validate_secrets(self):
        """启动时校验密钥，缺失则拒绝启动，避免用空密钥签发 JWT"""
        if not self.LLM_API_KEY:
            raise ValueError(
                "LLM_API_KEY 未配置。请在 .env 中设置，或通过环境变量传入。"
                "禁止用空密钥运行。"
            )
        if len(self.JWT_SECRET) < 32:
            raise ValueError(
                "JWT_SECRET 未配置或太短（至少 32 字符）。请在 .env 中设置，"
                "可用: python -c \"import secrets; print(secrets.token_hex(32))\" 生成。"
            )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # 测试场景可通过环境变量跳过校验（比如 CI 用固定测试密钥，或纯逻辑单测）
        if not os.environ.get("SKIP_SECRET_VALIDATION"):
            self._validate_secrets()


settings = Settings()
```

### 这段代码解决什么问题

整个项目有几十个"要变的东西"：数据库地址、Redis 端口、用哪个 LLM、密钥、分块大小……如果散落在各个文件里，改配置要满世界找，还容易把密码硬编码进代码。`config.py` 把所有配置**集中到一个类**里，启动时自动从 `.env` 读取。任何文件想用配置，只需 `from app.config import settings`。

### 关键代码逐句拆解

**① `PROJECT_ROOT = Path(__file__).resolve().parents[2]`**

找"项目根目录"：`__file__` 是当前文件路径（`.../backend/app/config.py`），`.resolve()` 解析成绝对路径，`.parents[2]` 往上走 2 层（`parents[0]`=app，`parents[1]`=backend，`parents[2]`=项目根目录）。这样无论从哪个目录启动程序，`.env` 都能被找到。

**② `class Settings(BaseSettings)` — Pydantic 的三大超能力**

- **类型校验**：`MYSQL_PORT: int` 如果 `.env` 里写了 `abc`，启动即报错，而不是运行到一半才炸。
- **自动读环境变量**：字段名 `MYSQL_HOST` 自动匹配同名环境变量。
- **自动读 `.env` 文件**：`model_config = SettingsConfigDict(env_file=...)` 指定路径（Pydantic v2 的写法；v1 是 `class Config`）。

三者合一：**代码里只写默认值，真正的配置从 `.env` 注入，类型错了立刻报错。**

**③ 字段带默认值的类型注解**

```python
MYSQL_HOST: str = "localhost"
REDIS_CACHE_TTL: int = 300
DEBUG: bool = True
```

Pydantic 会在运行时做**强制类型转换**：`.env` 里的 `"300"` 字符串会被转成 `300` 整数。

**③.5 两个知识库路径**

```python
REPO_PATH: str = "./data/target_repo"       # tinydb 知识库：TinyDB 源码
PROJECT_SOURCE_PATH: str = "."               # project 知识库：本项目自身源码
```

`PROJECT_SOURCE_PATH` 是后来加的多知识库配置——`project` 知识库索引的是 Code Assistant Agent 自身源码，Docker 环境通过 Compose 把项目挂载为只读目录（见 `knowledge_bases.py`）。

**④ LLM 配置那几行注释 = 切换开关**

```python
# LLM_API_ENDPOINT: str = "http://localhost:11434/api/chat"  # Ollama
LLM_API_ENDPOINT: str = "https://api.deepseek.com/v1/chat/completions"
LLM_MODEL: str = "deepseek-v4-flash"
# LLM_MODEL: str = "gemma:7b"
```

想从 DeepSeek 切到本地 Ollama，改两行配置即可，业务代码零改动。这是"配置驱动"：把变化的东西从代码里剥离出来。

**④.5 Agent 受控执行预算（关键设计）**

```python
AGENT_MAX_STEPS: int = 4                  # 最多工具调用轮数
AGENT_MAX_DURATION_SECONDS: float = 75.0  # Agent 总时长预算（秒）
AGENT_LLM_TIMEOUT_SECONDS: float = 15.0   # 协调 LLM 单次调用超时
AGENT_LLM_MAX_RETRIES: int = 0            # 协调 LLM 重试次数（预算内不重试）
AGENT_TOOL_LLM_TIMEOUT_SECONDS: float = 12.0  # 工具内部 LLM 超时
AGENT_REQUEST_TIMEOUT_SECONDS: float = 80.0   # 整个 HTTP 请求超时
```

**这是"受控执行"设计**：Agent 不是无限循环，而是有一整套预算约束——步数上限、总时长、单次 LLM 超时、请求级超时。一旦超预算，harness 会用已检索到的证据生成降级回答（见 harness.py 的 `_finish_from_observations`），而不是无限挂起。这是"面向工程化演示的可靠性措施"——生产系统常见设计的基础实现。

**⑤ `model_config` 的 `env_file_encoding = "utf-8"`**

如果不指定，Windows 上默认 GBK 编码，含中文注释的 `.env` 会解析失败。这是真实踩过的坑。

**⑥ `_validate_secrets()` — 快速失败（fail fast）**

```python
if not self.LLM_API_KEY:
    raise ValueError("LLM_API_KEY 未配置。...")
if len(self.JWT_SECRET) < 32:
    raise ValueError("JWT_SECRET 未配置或太短（至少 32 字符）。...")
```

防止新手忘了配密钥，系统"成功启动"却用空密钥签发 JWT——那等于任何人拿任意 token 都能伪造身份。启动时就检查，缺了直接拒绝启动。

**⑦ `__init__` 里的测试后门**

```python
if not os.environ.get("SKIP_SECRET_VALIDATION"):
    self._validate_secrets()
```

正常启动校验密钥，但**跑单元测试时没有真密钥**。所以提供 `SKIP_SECRET_VALIDATION=1` 跳过校验。你在 `tests/test_fusion.py` 开头看到的两行：

```python
os.environ.setdefault("SKIP_SECRET_VALIDATION", "1")
os.environ.setdefault("JWT_SECRET", "test-secret-only-for-ci-0123456789abcdef")
```

这就是"测试隔离"：测试环境和生产环境的配置分开。

**⑧ 模块级单例 `settings = Settings()`**

文件底部直接创建全局实例，全项目 `from app.config import settings` 拿到的都是同一个对象，配置只加载一次。

### 面试答题要点

> **Q：为什么用 pydantic-settings 而不是 `os.getenv()`？**
> 答：类型校验 + 自动读 `.env` + 字段带默认值。`os.getenv()` 拿到的都是字符串，类型转换得自己写，还容易忘。

> **Q：密钥怎么管理？**
> 答：密钥只放 `.env`，`.env` 在 `.gitignore` 里（不提交到仓库），用 `secrets.token_hex(32)` 生成。启动时 `_validate_secrets()` 校验缺失即报错，杜绝空密钥运行。

> **Q：测试和开发环境配置怎么隔离？**
> 答：CI 里通过环境变量 `SKIP_SECRET_VALIDATION=1` 跳过密钥校验，测试文件自己设置固定测试密钥；数据库/Redis 地址由 CI 服务容器提供，互不污染。

### 动手做

```bash
# 1. 复制环境变量模板
cp .env.example .env
# 2. 生成一个安全的 JWT 密钥
python -c "import secrets; print(secrets.token_hex(32))"
# 3. 填入 .env 后，试试不填 LLM_API_KEY 启动，观察报错
cd backend && python -c "from app.config import settings; print(settings.LLM_MODEL)"
```

---

## 1.2 logger.py — 监控探头

### 完整代码

```python
"""统一日志配置"""

import logging
import sys


def setup_logger(name: str = "code_assistant") -> logging.Logger:
    """创建统一格式的 logger"""
    logger = logging.getLogger(name)

    if not logger.handlers:
        logger.setLevel(logging.INFO)

        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(logging.INFO)

        formatter = logging.Formatter(
            "[%(name)s] %(levelname)s [%(module)s.%(funcName)s] %(message)s",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger


# 全局默认 logger
log = setup_logger()
```

### 这段代码解决什么问题

代码里到处是 `log.info(...)`、`log.warning(...)`。这个文件定义"log"从哪来、长什么样。用 `logging` 而不是 `print`，好处是**分级**（debug/info/warning/error）、**格式化**、**统一出口**。

### 关键代码逐句拆解

**① `logging.getLogger(name)` — 单例工厂**

同名 logger 只创建一次。第二次调用返回同一个对象。

**② `if not logger.handlers:` — 防重复添加**

因为 `setup_logger` 可能被多次调用（模块重复 import），如果每次都 `addHandler`，日志会被打印多遍。先检查已有 handler 就不再添加。

**③ `StreamHandler(sys.stdout)` — 输出到标准输出**

Docker 容器里 `docker logs` 能抓到 stdout。生产部署日志不写文件，走 stdout 是容器规范。

**④ Formatter 格式设计**

```python
"[%(name)s] %(levelname)s [%(module)s.%(funcName)s] %(message)s"
```

输出示例：

```
[code_assistant] INFO [fusion.hybrid_search] Dense: 10 results, Sparse: 10 results
```

`module` + `funcName` 自动带上"哪条日志来自哪个文件的哪个函数"，排查问题直接定位代码位置。

**⑤ 模块级 `log = setup_logger()`**

文件底部创建全局单例，任何文件 `from app.logger import log` 直接用。

### 面试答题要点

> **Q：为什么不直接 print？**
> 答：print 无法分级、无法统一格式、容器环境难管理。logging 自带级别控制（INFO/WARNING/ERROR），且每条日志能自动带上模块和函数名，配合 Docker 的 stdout 收集方案，可观测性更好。

> **Q：日志格式为什么带模块名？**
> 答：一个系统几十个模块，报错时能立刻知道日志来自哪个文件哪个函数，不用全局搜。这也是"可观测性"的基础——项目后面还有数据库级的日志（agent_logs / retrieval_logs），是日志的"持久化版"。

---

## 1.3 database.py — 管道系统

### 完整代码

```python
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession , async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

# 异步 MySQL 连接 URL：mysql+aiomysql://user:pass@host:port/db
DATABASE_URL = (
    f"mysql+aiomysql://{settings.MYSQL_USER}:{settings.MYSQL_PASSWORD}"
    f"@{settings.MYSQL_HOST}:{settings.MYSQL_PORT}/{settings.MYSQL_DATABASE}"
)

engine = create_async_engine(
    DATABASE_URL,
    echo = settings.DEBUG
)

async_session_factory = async_sessionmaker(
    engine,
    class_= AsyncSession,
    expire_on_commit=False
)

class Base(DeclarativeBase):
    """
    所有ORM类型的基类
    """
    pass

async def get_db():
    """FASTAPI依赖注入：每次请求都创建一个数据库会话"""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()

        except Exception:
            await session.rollback()
            raise

        finally:
            await session.close()
```

### 这段代码解决什么问题

搭好连接 MySQL 的"管道"，并提供一个 FastAPI 依赖注入函数 `get_db`，让每个请求都有独立、安全、自动提交/回滚的数据库会话。

### 关键代码逐句拆解

**① `DATABASE_URL` — 连接串**

拼出来是 `mysql+aiomysql://root:123456@localhost:3306/code_assistant`。协议 `mysql+aiomysql` 里的 **aiomysql 是异步驱动**，和后面的 `create_async_engine` 配套——**整条链路是异步的**。

为什么强调异步？FastAPI 的卖点是高并发。同步数据库调用会阻塞事件循环——一个请求在等数据库，其他几百个请求全部卡住。异步驱动让等待不阻塞其他请求。

**② `engine` — 连接池**

```python
engine = create_async_engine(DATABASE_URL, echo=settings.DEBUG)
```

`engine` 是 SQLAlchemy 的连接池：预先维护一批到 MySQL 的连接，需要时取、用完还，避免每个请求新建 TCP 连接（很贵）。

`echo=settings.DEBUG`：DEBUG 模式下打印每一条执行的 SQL。**开发时你能直接看到 ORM 翻译成了什么 SQL**——理解 ORM 行为最好的方式。生产关掉 DEBUG 就不刷屏。

**③ `async_session_factory` — 会话工厂**

`engine` 管"连接"，`session` 管"一次业务操作"。`async_sessionmaker` 是会话工厂，每次 `async_session_factory()` 生成一个新会话。

`expire_on_commit=False` 是性能/坑位细节：默认 SQLAlchemy 在 `commit()` 后会让已加载对象"过期"，下次访问属性要重新查库；异步场景下过期对象在事务外访问会报错。设成 `False`，commit 后属性仍可用。

**④ `class Base(DeclarativeBase)` — 所有表的祖宗**

后面每个模型文件都 `from app.database import Base`，然后 `class User(Base): ...`。SQLAlchemy 收集所有继承 `Base` 的类，最终在 `main.py` 的 `Base.metadata.create_all` 统一建表。

**⑤ `get_db()` — 依赖注入的核心**

```python
async def get_db():
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
```

`yield` 是 FastAPI 依赖注入的关键，执行顺序：

```
请求到达 → 创建 session → yield 交给路由使用
        → 路由处理完 → commit() 保存修改
        → 路由抛异常 → rollback() 回滚并重新抛出
        → finally 里 close() 关闭会话
```

这个函数替路由干了三件脏活：**开会话、自动提交、出错回滚**。路由只管 `session.add(...)`，不用写 commit。异常路径保证数据库不会处于"改了一半"的状态——这就是事务的原子性。

### 面试答题要点

> **Q：项目里怎么管理数据库连接？**
> 答：SQLAlchemy 异步引擎（create_async_engine + aiomysql）维护连接池；每次请求通过 FastAPI 依赖注入 `get_db()` 获取独立 AsyncSession，依赖注入自动 commit / rollback / close，路由代码不关心事务生命周期。

> **Q：为什么用异步数据库驱动？**
> 答：FastAPI 是异步框架，如果数据库调用是同步的，会阻塞事件循环，高并发下整个服务卡住。aiomysql 让数据库等待期间可以处理其他请求。

> **Q：`expire_on_commit=False` 是干嘛的？**
> 答：默认提交后对象会过期，异步环境下在事务外访问过期属性会报错；设为 False 后提交后仍能安全访问对象属性。

> **Q：Base.metadata.create_all 在哪个文件触发？**
> 答：`main.py` 的 `lifespan` 启动钩子里，`async with engine.begin() as conn: await conn.run_sync(Base.metadata.create_all)`，应用启动时自动建表。

### 动手做

```bash
# 启动依赖（仅 MySQL + Redis，不启后端）
docker compose up mysql redis

# 在后端目录里触发一次建表，观察 echo 打印的 SQL
cd backend
python -c "
import asyncio
from app.database import engine, Base
async def main():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()
asyncio.run(main())
"
```

### 第 1 层小结

三兄弟互相咬合：`config.py` 提供 `settings` → `database.py` 用它拼连接串；`logger.py` 提供 `log`；`database.py` 提供 `engine` / `async_session_factory` / `Base` / `get_db`。后面**每一个文件**都会引用它们。

---

# 第 2 层 数据模型：9 张表的仓库

第 1 层搭好了地基，这一层来建"货架"——**数据要存成什么样子**。这 9 张表是整个系统所有信息的载体：

| 表 | 存什么 | 谁在读 |
|----|--------|--------|
| `users` | 注册用户 | 鉴权、所有接口 |
| `conversations` / `messages` | Agent 会话和消息 | 对话接口 |
| `agent_logs` | Agent 每一步决策 | 可观测 / 排查 |
| `retrieval_logs` | 每次检索的完整链路 | 可观测 |
| `query_rewrites` | 查询改写记录 | 评估 / 调优 |
| `evaluation_runs` | 消融实验的指标 | 评估报告 |
| `index_versions` | 索引构建历史 | 索引管理 |
| `feedbacks` | 用户对回答的点赞/点踩 | 效果反馈 |

**共通的"表设计语言"**（读懂了这些，8 个文件基本是套路）：

1. **继承 `Base`**：`class User(Base)`，`from app.database import Base`。
2. **`__tablename__`**：显式指定表名。
3. **字段用 `Column(类型, 约束, comment=...)`** 定义。
4. **每个表都有 `id` 主键**：`Column(Integer, primary_key=True, autoincrement=True)`。
5. **几乎每个表都有 `created_at`**：`default=lambda: datetime.datetime.now(UTC)`——注意是**传函数引用**而不是直接调 `now()`，这样每条记录插入时才取最新时间，而不是模块加载时的时间。这个细节面试常考。

开始逐个看。

---

## 2.1 models/__init__.py — 模型的汇总清单

### 完整代码

```python
from app.models.conversation import Conversation, Message
from app.models.feedback import Feedback
from app.models.index_version import IndexVersion
from app.models.retrieval_log import RetrievalLog
from app.models.query_rewrite import QueryRewrite
from app.models.evaluation_run import EvaluationRun
from app.models.agent_log import AgentLog
from app.models.user import User

__all__ = ["Conversation", "Message", "Feedback", "IndexVersion", "RetrievalLog", "QueryRewrite" ,"EvaluationRun" ,"AgentLog" , "User"]
```

### 这段代码解决什么问题

把 8 个模型文件里的类**汇总到一个入口**。这样别处只需要 `from app.models import User`，不用记每个类在哪个文件。

它还有个**隐藏但关键的作用**：`main.py` 里 `Base.metadata.create_all` 建表时，SQLAlchemy 必须**先知道有哪些模型**。如果某个模型类从未被 import，它就不会注册到 `Base.metadata` 里，建表就会漏掉那张表。`__init__.py` 把 8 个模型全 import 一遍，确保建表时一个不漏。

**`__all__`** 是 Python 的"白名单"：`from app.models import *` 时只导入列出的名字；也给 IDE 提示了公开 API。

---

## 2.2 user.py — 用户表

### 完整代码

```python
"""用户模型"""

import datetime
from datetime import UTC

from sqlalchemy import Column, Integer, String, Boolean, DateTime
from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(32), unique=True, nullable=False, index=True, comment="用户名")
    hashed_password = Column(String(128), nullable=False, comment="bcrypt 哈希密码")
    role = Column(String(16), default="user", comment="角色: user / admin")
    is_active = Column(Boolean, default=True, comment="是否激活")
    created_at = Column(DateTime, default=lambda: datetime.datetime.now(UTC), comment="创建时间")
```

### 关键字段逐个讲

| 字段 | 设计 | 为什么 |
|------|------|--------|
| `username` | `String(32)` + `unique=True` + `index=True` | 用户名唯一；注册时查重靠它；加索引让按用户名查登录飞快 |
| `hashed_password` | `String(128)` | **只存 bcrypt 哈希，绝不存明文**。bcrypt 输出约 60 字符，给 128 留足空间 |
| `role` | `String(16)` 默认 `"user"` | 预留角色系统（user/admin），当前鉴权只用 `is_active`，但字段留着为扩展 |
| `is_active` | `Boolean` 默认 `True` | 账号禁用开关，`get_current_user` 里检查 `not user.is_active` 就拒绝 |
| `created_at` | `default=lambda: ...now(UTC)` | 见第 2 层开头的"共通语言" |

**为什么用户名加索引？** 登录流程是 `select(User).where(User.username == req.username)`——没有索引就是全表扫描；有 `index=True` 走 B+ 树索引，O(log n)。

---

## 2.3 conversation.py — 会话与消息表

### 完整代码

```python
import datetime
from datetime import UTC

from sqlalchemy import Column, Integer, String, DateTime, JSON, Text, UniqueConstraint
from app.database import Base


class Conversation(Base):
    """一次对话session"""
    __tablename__ = "conversations"
    __table_args__ = (
        # 同一用户 + 同一 session_id 唯一，防止并发创建重复会话
        UniqueConstraint("user_id", "session_id", name="uq_conversation_user_session"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, index=True, comment="所属用户ID")
    session_id = Column(String(64), nullable=False, index=True, comment="会话ID")
    created_at = Column(DateTime, default=datetime.datetime.utcnow, comment="创建时间")
    updated_at = Column(
        DateTime,
        default=lambda: datetime.datetime.now(UTC),
        onupdate=lambda: datetime.datetime.now(UTC),
        comment="最后更新时间",
    )


class Message(Base):
    """对话中的单条消息"""
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, index=True, comment="所属用户ID")
    session_id = Column(String(64), nullable=False, index=True, comment="所属会话ID")
    role = Column(String(16), nullable=False, comment="角色: user / assistant")
    content = Column(Text, nullable=False, comment="消息内容")
    tool_calls = Column(JSON, nullable=True, comment="Agent 调用的工具信息（JSON）")
    created_at = Column(DateTime, default=lambda: datetime.datetime.now(UTC), comment="发送时间")
```

### 关键设计逐个讲

**① 为什么 `conversations` 和 `messages` 两张表？**

一个会话（Conversation）包含多条消息（Message），这是**一对多**关系。拆两张表的好处：会话只存元信息（创建时间、更新时间），消息存内容；查"有哪些会话"不用扫描所有消息；一个会话上千条消息也能轻松加载最近 N 条。

**② `UniqueConstraint("user_id", "session_id")` — 数据库层兜底**

```python
__table_args__ = (
    UniqueConstraint("user_id", "session_id", name="uq_conversation_user_session"),
)
```

同一用户 + 同一 session 只允许一条会话记录。即使应用层并发创建重复会话（`get_or_create_conversation` 里先查后建存在竞态），数据库也会拒绝第二条，从根上防重复。

**③ `user_id` 和 `session_id` 都加索引**

每次查历史 `where(user_id=?, session_id=?)`，两个索引让查询高效。

**④ `updated_at` 用 `onupdate`**

```python
onupdate=lambda: datetime.datetime.now(UTC)
```

`onupdate` 在**记录被 UPDATE 时自动刷新时间**，配合 `default`（插入时）。很多系统喜欢把"最后活跃时间"放会话表，方便展示/清理。

**⑤ `Message.tool_calls` 是 JSON 字段**

`Column(JSON)` 存 Agent 调用了什么工具。虽然当前 `conversation_service` 还没往里写数据，但字段预留了，说明设计者想到"消息里可能带工具调用详情"。

**⑥ `Message.role` 只有 user / assistant**

注意：这个系统把 Agent 内部的工具调用过程放在 `agent_logs` 表，而 `messages` 只存最终问答。所以 `role` 两个值够用。

---

## 2.4 agent_log.py — Agent 决策日志

### 完整代码

```python
"""Agent 决策日志：记录每次 Agent 运行的每步决策链路"""

import datetime
from datetime import UTC

from sqlalchemy import Column, Integer, String, Text, DateTime
from app.database import Base


class AgentLog(Base):
    __tablename__ = "agent_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(64), nullable=False, index=True, comment="会话ID")
    step_number = Column(Integer, nullable=False, comment="第几步")
    thought = Column(Text, nullable=True, comment="LLM 的思考过程")
    action_name = Column(String(32), nullable=True, comment="调用的工具名")
    action_args = Column(Text, nullable=True, comment="工具参数（JSON）")
    observation = Column(Text, nullable=True, comment="工具返回结果摘要")
    created_at = Column(
        DateTime, default=lambda: datetime.datetime.now(UTC), comment="创建时间"
    )
```

### 这段代码解决什么问题

这是"**Agent 的黑匣子**"。ReAct 循环每走一步，`harness.py` 的 `_log_step` 就往这张表插一条：LLM 想了什么（`thought`）、调了哪个工具（`action_name`）、参数是什么（`action_args`）、工具返回了什么（`observation`）。

对应 README 里的"三层可观测性"之一。出问题时，你能把一次 Agent 运行**逐步回放**：它在第 2 步搜了 `JSONStorage`，观察结果如何，为什么第 4 步决定给答案。这种能力在面试讲"可观测性"时非常好用。

`step_number` 记录第几步；`thought` 存 LLM 的完整思考文本（`harness.py` 里截断到 500 字符）；`observation` 截断到 200 字符——防止日志表无限膨胀。

---

## 2.5 retrieval_log.py — 检索日志

### 完整代码

```python
import datetime
from datetime import UTC

from sqlalchemy import Column , Integer , String , Text ,DateTime, JSON, Float
from app.database import Base


class RetrievalLog(Base):
    """检索日志：记录每次 hybrid_search 的完整链路"""
    __tablename__ = "retrieval_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    query_text = Column(Text, nullable=False, comment="用户原始查询")
    dense_top_k = Column(JSON, nullable=True, comment="Dense 路 top-k 结果")
    sparse_top_k = Column(JSON, nullable=True, comment="Sparse 路 top-k 结果")
    fused_top_n = Column(JSON, nullable=True, comment="RRF 融合后 top-n 结果")
    strategy = Column(String(32), default="hybrid", comment="检索策略")
    total_latency_ms = Column(Float, nullable=True, comment="总耗时（毫秒）")
    created_at = Column(
        DateTime, default=lambda: datetime.datetime.now(UTC), comment="创建时间"
    )
```

### 这段代码解决什么问题

RAG 的"黑匣子"。`fusion.py` 的 `async_hybrid_search` 每次跑完混合检索，就把三路中间结果**原样 JSON 化**存进来：

- `query_text`：用户原始查询
- `dense_top_k`：稠密路返回的前几条
- `sparse_top_k`：稀疏路返回的前几条
- `fused_top_n`：RRF 融合后的最终结果
- `strategy`：用的什么策略（hybrid 等）
- `total_latency_ms`：链路总耗时

**价值**：你可以回看任何一次检索——稠密路和稀疏路各返回了什么、融合后剩下什么、花了多少毫秒。分析"为什么某次检索结果不好"时，这表就是现场录像。`JSON` 列能直接存结构化列表，查询时原样取回。

---

## 2.6 query_rewrite.py — 查询改写记录

### 完整代码

```python
import datetime
from datetime import UTC

from sqlalchemy import Column, Integer, String, Text, DateTime
from app.database import Base


class QueryRewrite(Base):
    """查询改写记录：存原始查询、改写后查询、改写策略"""
    __tablename__ = "query_rewrites"

    id = Column(Integer, primary_key=True, autoincrement=True)
    original_query = Column(Text, nullable=False, comment="原始查询")
    rewritten_query = Column(Text, nullable=False, comment="改写后查询")
    strategy = Column(String(16), nullable=False, comment="改写策略: hyde / expand")
    created_at = Column(
        DateTime, default=lambda: datetime.datetime.now(UTC), comment="创建时间"
    )
```

### 这段代码解决什么问题

`query_rewriter.py` 用 HyDE / expand 改写查询时，把"原查询 → 改写后查询 → 策略"落库。**目的：积累改写的真实样本**。以后你可以分析：哪些查询被改写了、改成了什么、HyDE 生成的假设文档质量如何。这也是评估 HyDE 组件是否有用的数据基础。

注意 `strategy` 字段没有默认值、`nullable=False`——强制要求写记录时必须标明策略，否则数据不完整。

---

## 2.7 evaluation_run.py — 评估运行记录

### 完整代码

```python
import datetime
from datetime import UTC

from sqlalchemy import Column, Integer, String, Text, Float, JSON, DateTime
from app.database import Base

class EvaluationRun(Base):
    __tablename__ = "evaluation_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_name = Column(String(128), nullable=False, comment="评估名称，如 'baseline_no_rerank'")
    description = Column(Text, nullable=True, comment="评估描述")
    config = Column(JSON, nullable=False, comment="评估配置：哪些组件开启")
    test_set_size = Column(Integer, nullable=False, comment="测试集查询数量")
    hit_rate = Column(Float, nullable=True, comment="Hit Rate")
    mrr = Column(Float, nullable=True, comment="Mean Reciprocal Rank")
    ndcg = Column(Float, nullable=True, comment="NDCG@k")
    avg_latency_ms = Column(Float, nullable=True, comment="平均检索延迟")
    created_at = Column(
        DateTime, default=lambda: datetime.datetime.now(UTC), comment="创建时间"
    )
```

### 这段代码解决什么问题

消融实验（`evaluation.py` 的 `run_ablation`）跑完后，把每组实验的指标写进这张表。字段设计很有讲究：

- `run_name`：`ablation_v1_dense_only` 这种唯一标识。
- `config`：**JSON 字段存"这组实验开了哪些组件"**（`{"dense": true, "sparse": false, ...}`）——这样表格不用为每个组件建一列，新组件加进 config 即可，schema 不变。这是 JSON 字段的典型用法。
- `hit_rate` / `mrr` / `ndcg` / `avg_latency_ms`：三个质量指标 + 一个性能指标。
- `test_set_size`：测试集条数，便于横向比较不同规模的结果。

**价值**：README 里那张消融表就是从这里导出的。面试时说"我的每个组件都有评估数据支撑"，指的就是这条链路。

---

## 2.8 index_version.py — 索引版本记录

### 完整代码

```python
import datetime
from datetime import UTC
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from app.database import Base

class IndexVersion(Base):
    """索引版本记录：每次重建索引时插入一条"""
    __tablename__ = "index_versions"

    id = Column(Integer , primary_key=True, autoincrement=True)
    strategy = Column(String(32), comment="分块策略")
    chunk_size = Column(Integer, comment="块大小")
    chunk_overlap = Column(Integer, comment="块重叠")
    file_count = Column(Integer, comment="文件数")
    chunk_count = Column(Integer, comment="块数")
    build_duration_ms = Column(Integer, nullable=True, comment="构建耗时（毫秒）")
    created_at = Column(
        DateTime, default=lambda: datetime.datetime.now(UTC), comment="创建时间"
    )
```

### 这段代码解决什么问题

每次重建索引（`code_indexer.py` 的 `save_version_record`）记录一条：用了什么分块策略、多大、多少个文件、多少个 chunk、耗时多少。

**为什么有用？** 当你换了分块策略（比如从 recursive 换到 semantic），想对比"哪个策略检索效果更好"，得有据可查：当时的索引是用什么参数建的。这是索引的可追溯性——配合 `evaluation_runs` 就能做"索引配置 × 检索指标"的交叉分析。

注意这个文件顶部 import 了 `ForeignKey` 但没用——属于遗留 import，不影响功能，但面试时被问到可以大方指出这是可以清理的小瑕疵（诚实 + 细心）。

---

## 2.9 feedback.py — 用户反馈

### 完整代码

```python
import datetime
from datetime import UTC

from sqlalchemy import Column, Integer, String, Text, DateTime
from app.database import Base

class Feedback(Base):
    """用户对Agent回答的反馈(点赞/点踩)"""
    __tablename__ = "feedbacks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    message_id = Column(Integer, nullable=False, index=True, comment="对应消息ID")
    session_id = Column(String(64), nullable=False, comment="所属会话ID")
    rating = Column(Integer, nullable=False, comment="评分: 1=点赞, -1=点踩")
    comment = Column(Text, nullable=True, comment="用户可选评价文本")
    created_at = Column(DateTime, default=lambda: datetime.datetime.now(UTC), comment="创建时间")
```

### 这段代码解决什么问题

收集用户对 Agent 回答质量的反馈（点赞/点踩）。`rating` 用整数：`1` 点赞、`-1` 点踩。`message_id` 关联到具体那条消息（虽然当前没建外键约束，但字段语义明确）。`comment` 是可选补充说明。

**注意 `rating` 用整数而不是布尔**：为未来扩展留了余地（比如支持 1-5 星）。这个"用更宽的字段类型为扩展留空间"的思路值得学习。

### 第 2 层小结

9 张表（conversation.py 里定义了两张：Conversation 和 Message）可以分成三组记忆：

- **业务数据**：users、conversations、messages、feedbacks——系统的"正业"。
- **可观测数据**：agent_logs、retrieval_logs、query_rewrites——Agent 和检索的"黑匣子"。
- **工程数据**：evaluation_runs、index_versions——评估和索引的"台账"。

共同点：都有 `id` 主键、`created_at` 时间戳，都继承 `Base`。理解"每个表为什么存在"比背字段更重要——面试官问"你项目里有哪些表"，你要能说出**每张表服务的业务或可观测性目的**。

---

# 第 3 层 安全：鉴权与限流

地基和数据模型都齐了。但整栋楼现在是"裸奔"的——谁都能进来。第 3 层负责**装门禁**：

- `auth.py` —— 大门：你是谁？（JWT 鉴权 + bcrypt 密码哈希 + Redis 黑名单登出）
- `middleware.py` —— 闸机：你刷太快了？（Redis 滑动窗口限流）

这一层是面试含金量最高的部分之一，因为"安全"是后端岗位最看重的工程能力。

---

## 3.1 auth.py — JWT 鉴权全家桶

### 完整代码

```python
"""JWT 鉴权：创建/验证 token、密码哈希、依赖注入"""

import datetime
from datetime import UTC, timedelta
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
import bcrypt
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.config import settings
from app.database import get_db
from app.models.user import User

security = HTTPBearer()

# JWT 配置直接从 settings 读取，或硬编码默认值
SECRET_KEY = settings.JWT_SECRET
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 小时
REFRESH_TOKEN_EXPIRE_DAYS = 7

def hash_password(password: str) -> str:
    """bcrypt 哈希密码（原生 API）"""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证密码"""
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8"),
        )
    except ValueError:
        return False

def create_access_token(data: dict) -> str:
    """创建访问 token（短期）"""

    to_encode = data.copy()
    expire = datetime.datetime.now(UTC) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire , "type": "access"})
    return jwt.encode(to_encode , SECRET_KEY , algorithm=ALGORITHM)

def create_refresh_token(data: dict) -> str:
    """创建刷新 token（长期）"""

    to_encode = data.copy()
    expire = datetime.datetime.now(UTC) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def decode_token(token: str) -> dict:
    """解码 token，失败抛 401"""

    try:
        payload = jwt.decode(token, SECRET_KEY , algorithms=[ALGORITHM])
        return payload

    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expire token",
        )

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db:AsyncSession = Depends(get_db),
) -> User:
    """FastAPI 依赖注入：从请求头获取当前登录用户"""
    if is_token_blacklisted(credentials.credentials):
        raise HTTPException(status_code=401, detail="Token has been revoked")
    payload = decode_token(credentials.credentials)
    username = payload.get("sub")
    if not username:
        raise HTTPException(status_code=401 , detail="Invalid token") 

    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")
    return user

from app.clients import get_redis_client

def _get_redis():
    return get_redis_client()


def blacklist_token(token: str, expire_seconds: int):
    """把 token 加入 Redis 黑名单"""
    try:
        r = _get_redis()
        if r is None:
            return
        r.setex(f"blacklist:{token}", expire_seconds, "1")
    except Exception:
        pass


def is_token_blacklisted(token: str) -> bool:
    """检查 token 是否在黑名单中"""
    try:
        r = _get_redis()
        if r is None:
            return False
        return bool(r.exists(f"blacklist:{token}"))
    except Exception:
        return False
```

### 这段代码解决什么问题

"怎么证明你是你？"——这是鉴权的核心问题。方案是 **JWT**：用户登录成功后，服务端签发一个**签名过的 token**，客户端后续每次请求带上它，服务端验签即信。关键点：**JWT 是无状态的**——服务端不存 session，只靠签名判断真伪。

整体流程：

```
注册:  明文密码 ──bcrypt 哈希──► 存 hashed_password
登录:  输入密码 ──bcrypt 校验──► 通过则签发 access_token + refresh_token
请求:  每次带 Bearer token ──► get_current_user 解析出用户
登出:  把 token 塞进 Redis 黑名单，剩余有效期自动过期
```

### 关键代码逐句拆解

**① `security = HTTPBearer()` — 声明"我要从请求头拿 token"**

```python
security = HTTPBearer()
```

FastAPI 的 `HTTPBearer` 是一个安全方案：自动从请求头 `Authorization: Bearer <token>` 里解析出 token。配合 `get_current_user` 的参数 `credentials: HTTPAuthorizationCredentials = Depends(security)`，FastAPI 会在路由依赖里自动解析。请求没带 token 或格式不对，直接 401。

**② bcrypt 哈希（hash_password / verify_password）**

```python
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except ValueError:
        return False
```

- 密码**绝不存明文**。bcrypt 自带随机盐（`bcrypt.gensalt()`），同一个密码每次哈希结果都不同。
- `verify_password` 用 `try/except ValueError` 兜底：如果数据库里存的是 malformed 哈希（比如被截断），`checkpw` 会抛 `ValueError`，捕获后返回 `False`，而不是让服务崩溃。
- 返回 `.decode("utf-8")`：`hashpw` 返回 bytes，存数据库要转成 str。

**③ 双 token 设计**

```python
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 小时
REFRESH_TOKEN_EXPIRE_DAYS = 7

def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.datetime.now(UTC) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def create_refresh_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.datetime.now(UTC) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
```

- **access token** 短期（24h），用于正常请求鉴权。泄露了损失有限。
- **refresh token** 长期（7天），只在 `/refresh` 接口用，用于换取新的 access token。
- 两个 token 都往 payload 里塞了 **`type` 字段**：`access` / `refresh`。这样 `/refresh` 接口能校验"你给我的真的是 refresh token，不是拿 access token 来冒充"（见 auth_router.py）。
- **`to_encode = data.copy()`**：防止修改调用方传入的 dict（jwt.encode 内部可能修改传入对象）。
- 用 `datetime.now(UTC)`（带时区）而不是 `datetime.utcnow()`（已废弃），避免时区歧义。

**④ `decode_token` — 验签 + 失败抛 401**

```python
def decode_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expire token")
```

`jose`（python-jose）的 `jwt.decode` 会**同时验证签名和过期时间**。任何失败（签名不符、过期、格式错误）统一抛 `JWTError`，这里转成 401。注意 `algorithms=[ALGORITHM]` 显式指定算法——防止算法混淆攻击（不指定时某些库会接受 `none` 算法）。

**⑤ `get_current_user` — 依赖注入的鉴权枢纽**

```python
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    if is_token_blacklisted(credentials.credentials):
        raise HTTPException(status_code=401, detail="Token has been revoked")
    payload = decode_token(credentials.credentials)
    username = payload.get("sub")
    if not username:
        raise HTTPException(status_code=401, detail="Invalid token")

    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")
    return user
```

四道检查，层层过滤：

1. **Redis 黑名单**：先查 token 是否被登出过。
2. **验签 + 过期**：`decode_token`。
3. **payload 里有没有 `sub`**（用户名）——`sub` 是 JWT 标准声明，这里是用户名。
4. **用户存在且激活**：查库确认，同时检查 `is_active`。

**这是 FastAPI 依赖注入的典型用法**：任何路由只要声明 `current_user: User = Depends(get_current_user)`，就自动完成全部鉴权，路由内部拿到的 `current_user` 就是数据库里那个 `User` 对象。

**⑥ Redis 黑名单（登出能力）**

```python
def blacklist_token(token: str, expire_seconds: int):
    try:
        r = _get_redis()
        r.setex(f"blacklist:{token}", expire_seconds, "1")
    except Exception:
        pass


def is_token_blacklisted(token: str) -> bool:
    try:
        r = _get_redis()
        return bool(r.exists(f"blacklist:{token}"))
    except Exception:
        return False
```

JWT 无状态 = 签发后服务端不知道它"死没死"。**要支持登出，必须主动记住"哪些 token 作废了"**。

- `blacklist_token`：把 token 写进 Redis，key 是 `blacklist:<token>`，value `"1"`，**TTL = token 剩余有效期**。到点自动删除，不占空间。
- `is_token_blacklisted`：查 Redis 里有没有这个 key。
- `try/except Exception: pass`：Redis 不可用时**降级**——黑名单检查失败就当作"没被拉黑"，保证核心功能不因缓存故障而瘫。这是"可用性优先于强一致"的权衡。

`_get_redis` 里注意 `protocol=2`：指定 Redis 协议版本为 2，兼容更老的 Redis 服务端。

### 面试答题要点

> **Q：JWT 和传统 session 有什么区别？**
> 答：session 是服务端存状态、客户端存 session_id；JWT 是无状态的，服务端只靠签名验真伪。JWT 适合分布式/微服务（每个节点验签即可，不用共享 session 存储），代价是无法主动吊销（所以要配黑名单）。

> **Q：为什么用双 token？**
> 答：access token 短命（24h），即使泄露影响有限；refresh token 长命（7天）只用于换新 access。避免用户频繁登录，又控制泄露风险。refresh token 必须校验 `type == "refresh"`，防止 access token 冒充。

> **Q：JWT 怎么登出？**
> 答：JWT 无状态，登出时把 token 加入 Redis 黑名单，TTL 设为 token 剩余有效期；每次鉴权先查黑名单。Redis 自动过期，不用手动清理。

> **Q：密码为什么用 bcrypt 而不是 MD5/SHA？**
> 答：bcrypt 自带盐 + 计算慢（抗暴力破解）。MD5/SHA 是快速哈希，撞库成本低，且无盐时相同密码哈希相同。bcrypt 每次加随机盐，相同密码哈希也不同。

> **Q：Redis 挂了怎么办？**
> 答：黑名单检查失败就降级为"未拉黑"，保证核心功能可用。这是可用性优先的取舍——牺牲登出的强一致，换取服务不因缓存故障而瘫。

### 动手做

```bash
# 用 python 直接体验 JWT 生成与校验
cd backend
python -c "
from app.auth import create_access_token, decode_token
tok = create_access_token({'sub': 'hong'})
print('token:', tok[:40], '...')
print('payload:', decode_token(tok))
"
```

---

## 3.2 middleware.py — Redis 滑动窗口限流

### 完整代码

```python
"""Redis 滑动窗口限流中间件（基于 ZSET）"""

import time
import uuid

from fastapi import Request
from starlette.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from app.config import settings
from app.clients import get_redis_client
from app.logger import log


class RateLimitMiddleware(BaseHTTPMiddleware):
    """滑动窗口限流：每客户端在 window_seconds 内最多 rate_limit 次请求

    用 Redis ZSET 实现真正的滑动窗口：每个请求时间戳作为一个 member，
    每次检查时删除窗口外的旧记录，统计窗口内的数量。
    相比固定窗口（time()//window），滑动窗口不会在窗口边界产生突刺。
    """

    def __init__(
        self,
        app,
        rate_limit: int = 60,
        window_seconds: int = 60,
        redis_client=None,
    ):
        super().__init__(app)
        self.rate_limit = rate_limit
        self.window_seconds = window_seconds
        self.redis = redis_client
        if self.redis is not None:
            return

        self.redis = get_redis_client()
        if self.redis is None:
            log.warning("Redis unavailable, rate limiting disabled")

    def _client_key(self, request: Request) -> str:
        """识别客户端：优先从 JWT 解析用户，否则退回 IP。

        注意：中间件在鉴权依赖（get_current_user）之前运行，拿不到
        request.state.user，所以这里自己解析 Authorization 头。
        """
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth[len("Bearer "):]
            try:
                from app.auth import decode_token
                payload = decode_token(token)
                if payload.get("type") == "access":
                    return f"user:{payload.get('sub', 'unknown')}"
            except Exception:
                # token 无效或过期，退回 IP 限流
                pass
        return f"ip:{request.client.host}"

    async def dispatch(self, request: Request, call_next):
        if self.redis is None:
            return await call_next(request)

        # 只对 API 路径限流，跳过静态资源和文档
        if not request.url.path.startswith("/api/"):
            return await call_next(request)

        client = self._client_key(request)
        key = f"ratelimit:{client}"

        try:
            now = time.time()
            window_start = now - self.window_seconds
            pipeline = self.redis.pipeline()
            pipeline.zremrangebyscore(key, 0, window_start)  # 删窗口外旧记录
            pipeline.zadd(key, {uuid.uuid4().hex: now})       # 加当前请求
            pipeline.zcard(key)                              # 统计窗口内数量
            pipeline.expire(key, self.window_seconds + 1)
            _, _, count, _ = pipeline.execute()

            if count > self.rate_limit:
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Rate limit exceeded"},
                )
        except Exception as e:
            log.warning("Rate limit check failed: %s", e)

        return await call_next(request)
```

### 这段代码解决什么问题

防止有人**疯狂刷接口**（暴力破解密码、爬虫、恶意打爆服务）。限制：每个客户端在 60 秒窗口内最多 60 次请求，超过就返回 429。

**为什么要"滑动窗口"而不是"固定窗口"？** 固定窗口实现是 `time() // 60` 取分钟桶。问题：59.9 秒的请求和 60.1 秒的请求只差 0.2 秒，却被分到两个不同窗口，各能发 60 次——**实际 0.2 秒内可以发 120 次**，窗口边界产生"突刺"。滑动窗口没有这个漏洞。

### 关键代码逐句拆解

**① `BaseHTTPMiddleware` + `dispatch` — Starlette 中间件接口**

```python
class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, rate_limit=60, window_seconds=60):
        super().__init__(app)
        ...
    async def dispatch(self, request: Request, call_next):
        ...
```

`dispatch` 是中间件的入口：它在每个请求进入路由**之前**被调用。你可以在 `call_next(request)` 前后做文章——`call_next` 才是真正把请求交给路由。这里就是"先限流，超了就拦住，不超才放行"。

**② 客户端识别 `_client_key` — 关键设计**

```python
def _client_key(self, request: Request) -> str:
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        token = auth[len("Bearer "):]
        try:
            from app.auth import decode_token
            payload = decode_token(token)
            if payload.get("type") == "access":
                return f"user:{payload.get('sub', 'unknown')}"
        except Exception:
            pass
    return f"ip:{request.client.host}"
```

限流按"人"还是按"IP"？按 IP 有个问题：公司里很多人共享一个出口 IP，一个被限、全公司都 429。这个实现**优先按登录用户**限流（`user:<username>`），没登录才退回 IP。

**注意中间件执行时机**：它在鉴权依赖 `get_current_user` **之前**运行，所以 `request.state.user` 还没有。作者自己解析 `Authorization` 头 + `decode_token`。这是个容易踩的坑，代码注释里也写明了。

还有一个细节：只对 `type == "access"` 的 token 走用户限流——refresh token 不在请求头上当访问凭证，不参与。

**③ Redis ZSET 滑动窗口（核心算法）**

```python
now = time.time()
window_start = now - self.window_seconds
pipeline = self.redis.pipeline()
pipeline.zremrangebyscore(key, 0, window_start)  # ① 删掉窗口外的旧记录
pipeline.zadd(key, {uuid.uuid4().hex: now})       # ② 当前请求时间戳入 ZSET
pipeline.zcard(key)                              # ③ 数窗口内有几个请求
pipeline.expire(key, self.window_seconds + 1)
_, _, count, _ = pipeline.execute()

if count > self.rate_limit:
    return JSONResponse(status_code=429, content={"detail": "Rate limit exceeded"})
```

**ZSET（有序集合）** 每个元素是 `(member, score)`，按 score 排序。这里：
- **score = 请求到达的时间戳**（`time.time()`）
- **member = 随机 UUID**（保证每个请求唯一）

四步操作：
1. `zremrangebyscore(key, 0, window_start)`：删除 score 在 `[0, window_start]` 的记录——也就是**窗口外过期的旧请求**。
2. `zadd(key, {uuid: now})`：把当前请求加进集合。
3. `zcard(key)`：数集合里有多少个——就是**当前窗口内活着的请求数**。
4. `expire(key, window_seconds + 1)`：给 key 设过期，防止长期不活跃的 key 占用 Redis。

`count > rate_limit` 就返回 429。

**为什么要用 `pipeline`？** 这 4 个操作如果逐个发 Redis，要 4 次网络往返；pipeline 把 4 条命令打包一次发送，Redis 依次执行，一次返回结果。**显著降低网络开销**——限流逻辑要加在每个请求上，性能不能差。

**④ Redis 不可用时优雅降级**

```python
self.redis = None
try:
    ...
    self.redis.ping()
except Exception as e:
    log.warning("Redis unavailable, rate limiting disabled: %s", e)
```

```python
async def dispatch(self, request: Request, call_next):
    if self.redis is None:
        return await call_next(request)
```

Redis 连不上就**禁用限流**而不是拒绝所有请求。这与 auth.py 里的 `except Exception: pass` 是同一个哲学：**限流是保护措施，不能让保护措施本身把服务搞挂**。

**⑤ 只对 `/api/` 限流**

```python
if not request.url.path.startswith("/api/"):
    return await call_next(request)
```

静态资源、`/docs` 文档不参与限流，避免误伤开发者调试。

### 面试答题要点

> **Q：固定窗口和滑动窗口的区别？**
> 答：固定窗口按 `time()//window` 切桶，窗口边界会有突刺（59.9s 和 60.1s 的请求被算进两个窗口，各能满额）。滑动窗口基于 Redis ZSET 记录每个请求时间戳，每次动态删除窗口外记录再计数，边界连续、无突刺。

> **Q：滑动窗口用 ZSET 怎么实现？**
> 答：每个请求时间戳作为 score、UUID 作为 member 存入 ZSET；每次请求先 `zremrangebyscore` 删窗口外旧记录，再 `zadd` 当前请求，`zcard` 统计数量，超过阈值返回 429。用 pipeline 一次发送多条命令降低延迟。

> **Q：按用户限流还是按 IP 限流？**
> 答：两者结合。优先按登录用户（`user:<username>`），未登录退回 IP。因为中间件运行在鉴权之前，拿不到 request.state.user，所以自己解析 Authorization 头。

> **Q：Redis 挂了怎么办？**
> 答：限流中间件初始化失败时置 `redis=None`，dispatch 里直接放行，保证服务可用。限流是保护措施，不能成为单点故障。

> **Q：为什么用 Redis 而不是本地内存？**
> 答：多实例部署时本地内存各自独立，限流会失效；Redis 是共享存储，所有实例看到同一份计数。且 ZSET 的滑动窗口逻辑天然适合 Redis 实现。

### 动手做

```bash
# 手动体验 ZSET 滑动窗口
redis-cli
# 然后依次执行：
# ZADD ratelimit:demo 100 a 200 b 300 c
# ZCARD ratelimit:demo
# ZREMRANGEBYSCORE ratelimit:demo 0 150
# ZCARD ratelimit:demo   # 看到 2（b、c 还在）
```

## 3.3 clients.py — 共享客户端（进程级单例）

### 完整代码

```python
"""Process-wide clients shared by cache, rate limiting, and retrieval."""

from threading import Lock

import redis as redis_lib
from redis.backoff import NoBackoff
from redis.retry import Retry

from app.config import settings
from app.logger import log

_redis_client = None
_redis_initialized = False
_redis_lock = Lock()


def get_redis_client():
    """Create one Redis client/connection pool for this backend process."""
    global _redis_client, _redis_initialized
    with _redis_lock:
        if _redis_initialized:
            return _redis_client

        _redis_initialized = True
        try:
            client = redis_lib.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                db=0,
                decode_responses=True,
                protocol=2,
                socket_connect_timeout=0.2,
                socket_timeout=0.2,
                retry=Retry(NoBackoff(), retries=0),
            )
            client.ping()
            _redis_client = client
        except Exception as exc:
            log.warning("Redis unavailable, shared client disabled: %s", exc)
            _redis_client = None
        return _redis_client
```

### 这段代码解决什么问题

**让整个后端进程只维护一个 Redis 客户端/连接池**，供鉴权黑名单、限流中间件、检索缓存、BM25 恢复等多处复用。这是"共享基础设施"的集中管理。

**为什么重要**：早期版本每个模块（auth、middleware、dense_retriever、sparse_retriever、reranker）都自己 `redis_lib.Redis(...)` 建连接——一个进程可能建好几个 Redis 连接，浪费资源，配置还不统一。`clients.py` 把这些统一成**一个惰性初始化的进程级单例**。

### 关键代码逐句拆解

**① 线程安全的惰性单例**

```python
_redis_client = None
_redis_initialized = False
_redis_lock = Lock()

def get_redis_client():
    global _redis_client, _redis_initialized
    with _redis_lock:
        if _redis_initialized:
            return _redis_client
        _redis_initialized = True
        try:
            client = redis_lib.Redis(...)
            client.ping()
            _redis_client = client
        except Exception as exc:
            _redis_client = None
        return _redis_client
```

- **`_redis_initialized` 标记**：只初始化一次（双检查——外层函数判断 + 锁内再判断，避免并发下重复创建）。
- **`Lock` 保证线程安全**：FastAPI 的 `asyncio.to_thread` 会开多线程，多个线程同时调 `get_redis_client()` 时，锁防止重复创建连接。
- **短超时 + 不重试**（`socket_connect_timeout=0.2` / `socket_timeout=0.2` / `retry=Retry(NoBackoff(), retries=0)`）：Redis 挂掉时快速失败，不让所有依赖 Redis 的模块卡住等待。
- **失败置 None**：Redis 不可用时返回 `None`，调用方各自降级（黑名单不检查、限流不禁用、缓存不生效）。

**② 谁在用 `get_redis_client()`**

- `auth.py` 的黑名单（`blacklist_token` / `is_token_blacklisted`）
- `middleware.py` 的限流（RateLimitMiddleware）
- `sparse_retriever.py` 的 BM25 缓存
- `reranker.py` 的缓存

**关键点**：这些模块**不再各自 new Redis 连接**，统一走 `get_redis_client()`。改 Redis 配置只动一处。

### 面试答题要点

> **Q：为什么 Redis 客户端要做成进程级单例？**
> 答：避免每个模块各自建连接——多个连接浪费资源、配置不统一。用 `Lock` + 惰性初始化保证线程安全且只建一次。FastAPI 多线程下，锁防止并发重复创建。

> **Q：Redis 挂了会怎样？**
> 答：`get_redis_client` 失败返回 `None`，各调用方优雅降级——黑名单不检查（登出失效但可用）、限流不禁用、缓存不生效。这是"保护措施不能成为单点故障"的设计。

> **Q：为什么短超时 + 不重试？**
> 答：Redis 是高频依赖，挂掉时如果每个请求都等长超时 + 重试，会把整个服务拖垮。短超时（0.2s）快速失败，让依赖方立即走降级路径。

### 第 3 层小结

`auth.py` 管"你是谁"（身份），`middleware.py` 管"你刷多快"（频率），`clients.py` 管"共用一根管子"（共享 Redis 客户端）。三个文件都体现了**降级优先**的设计：Redis 挂了，鉴权黑名单降级为不检查、限流降级为不禁用。这个"保护措施不能成为单点故障"的思路，是面向工程化演示的可靠性设计，面试官会喜欢。

---

# 第 4 层 RAG 检索管线

第 4 层是**项目的技术核心**，也是面试里最能展示深度的地方。RAG（Retrieval-Augmented Generation，检索增强生成）的完整链路是：

```
离线阶段：建索引
  源码 ──► chunker 分块 ──► 稠密向量存 Chroma + BM25 索引存 Redis
在线阶段：查索引
  问题 ──► 改写（HyDE，可选）──► 双路召回 ──► RRF 融合 ──► 重排（可选）──► 结果
评估阶段：验证
  20 条测试集 ──► 5 组消融实验 ──► Hit Rate / MRR / NDCG 指标
```

这一层有 10 个文件，我按"在线链路 → 离线编排 → 评估"的顺序讲：

- 在线链路（用户查询时跑）：chunker → dense_retriever → sparse_retriever → fusion → query_rewriter → reranker
- 离线编排：code_indexer、user_upload
- 评估：test_set、evaluation

---

## 4.1 chunker.py — 代码分块器

### 完整代码

```python
from typing import Any

from langchain_text_splitters import RecursiveCharacterTextSplitter, TokenTextSplitter

from app.config import settings


class CodeChunker:
    """代码分块器，根据 strategy 配置选择不同分块策略"""

    def __init__(
        self,
        strategy: str = "recursive",
        chunk_size: int = 500,
        chunk_overlap: int = 50,
    ):
        self.strategy = strategy
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def chunk(self, documents: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if self.strategy == "recursive":
            return self._recursive_chunk(documents)
        elif self.strategy == "token":
            return self._token_chunk(documents)
        elif self.strategy == "semantic":
            return self._semantic_chunk(documents)
        else:
            raise ValueError(f"Unknown chunk strategy: {self.strategy}")

    def _recursive_chunk(self, documents: list[dict]) -> list[dict]:
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            separators=["\n\n", "\n", "def ", "class ", "    ", " "],
        )
        return self._apply_splitter(splitter, documents)

    def _token_chunk(self, documents: list[dict]) -> list[dict]:
        splitter = TokenTextSplitter(
            chunk_size=self.chunk_size // 4,
            chunk_overlap=self.chunk_overlap // 4,
        )
        return self._apply_splitter(splitter, documents)

    def _semantic_chunk(self, documents: list[dict]) -> list[dict]:
        chunks = []
        for doc in documents:
            lines = doc["content"].split("\n")
            current_chunk_lines: list[str] = []
            for line in lines:
                if (line.startswith("def ") or line.startswith("class ")) and current_chunk_lines:
                    indent = len(line) - len(line.lstrip())
                    if indent == 0:
                        text = "\n".join(current_chunk_lines)
                        if text.strip():
                            chunks.append({
                                "text": text,
                                "metadata": {
                                    "source": doc["path"],
                                    "chunk_index": len(chunks),
                                },
                            })
                        current_chunk_lines = []
                current_chunk_lines.append(line)
            if current_chunk_lines:
                text = "\n".join(current_chunk_lines)
                if text.strip():
                    chunks.append({
                        "text": text,
                        "metadata": {
                            "source": doc["path"],
                            "chunk_index": len(chunks),
                        },
                    })
        return chunks

    def _apply_splitter(self, splitter, documents: list[dict]) -> list[dict]:
        chunks = []
        for doc in documents:
            texts = splitter.split_text(doc["content"])
            for i, text in enumerate(texts):
                chunks.append({
                    "text": text,
                    "metadata": {
                        "source": doc["path"],
                        "chunk_index": i,
                    },
                })
        return chunks

    def info(self) -> dict:
        return {
            "strategy": self.strategy,
            "chunk_size": self.chunk_size,
            "chunk_overlap": self.chunk_overlap,
        }
```

### 这段代码解决什么问题

Embedding 模型有输入长度限制，而且"一个函数"比"整个文件"更适合精确检索。所以**建索引前必须把大文件切成小块**。这个类根据配置 `CHUNK_STRATEGY` 切换三种分块策略。

### 关键代码逐句拆解

**① 入口 `chunk()` — 策略路由**

```python
def chunk(self, documents):
    if self.strategy == "recursive":
        return self._recursive_chunk(documents)
    elif self.strategy == "token":
        return self._token_chunk(documents)
    elif self.strategy == "semantic":
        return self._semantic_chunk(documents)
    else:
        raise ValueError(f"Unknown chunk strategy: {self.strategy}")
```

`documents` 是 `[{path, content}]` 结构。未知策略直接抛 `ValueError`（fail fast）。

**② 统一输出格式：`{text, metadata}`**

所有策略最后都输出统一结构：

```python
{
    "text": "代码片段内容",
    "metadata": {
        "source": "tinydb/storages.py",   # 来源文件
        "chunk_index": 0,                  # 第几个块
    },
}
```

**`metadata` 是检索结果的"身份证"**——后面融合、去重、定位文件全靠 `source` + `chunk_index` 这一对 key。

**③ recursive 策略 — 通用默认**

```python
splitter = RecursiveCharacterTextSplitter(
    chunk_size=self.chunk_size,
    chunk_overlap=self.chunk_overlap,
    separators=["\n\n", "\n", "def ", "class ", "    ", " "],
)
```

`RecursiveCharacterTextSplitter` 按优先级依次尝试分隔符：段落 → 换行 → **`def `/`class `** → 缩进 → 空格。如果一段太长，就再往下拆。`chunk_overlap=50` 让相邻块有 50 字符重叠——**避免在边界处切断一个函数名/语句**。

**④ token 策略**

```python
splitter = TokenTextSplitter(
    chunk_size=self.chunk_size // 4,
    chunk_overlap=self.chunk_overlap // 4,
)
```

按 token 数切。`//4` 是估算：英文大概 4 个字符 ≈ 1 个 token，所以 `500 字符 ≈ 125 token`。

**⑤ semantic 策略 — 手写按函数边界切（亮点）**

```python
for line in lines:
    if (line.startswith("def ") or line.startswith("class ")) and current_chunk_lines:
        indent = len(line) - len(line.lstrip())
        if indent == 0:   # 只有顶格定义才切，类里的方法不切
            ...把 current_chunk_lines 存成一块...
    current_chunk_lines.append(line)
```

逻辑：逐行扫描，遇到**顶格**（`indent == 0`）的 `def `/`class ` 就认为上一个函数/类结束，把累积的行存成一块。

**为什么只切顶格？** 因为类里的方法（有缩进的 `def`）应该留在类里，不单独成块——不然一个类被拆得七零八落，检索到方法却丢了类的上下文。`indent == 0` 这个判断很精准。

**⑥ `info()`**

返回分块配置（strategy / size / overlap），用于记录索引版本。

### 面试答题要点

> **Q：为什么要分块？分块多大合适？**
> 答：Embedding 模型有最大输入长度；且块越小检索越精确（"一个函数"比"整个文件"好匹配）。但块太小会丢失上下文。项目用 500 字符 + 50 重叠，代码场景比通用文本更关注函数边界。

> **Q：三种分块策略的区别？**
> 答：recursive 按分隔符优先级递归切，通用；token 按 token 数切，对模型上下文窗口友好；semantic（代码版）按顶格 def/class 切，每个 chunk 大概率是一个完整函数或类。代码场景下 semantic 更合适。

> **Q：overlap 是干嘛的？**
> 答：相邻块重叠一部分文本，避免在边界切断关键代码（如函数签名、语句）。切断了检索匹配就失败。

> **Q：metadata 里 source 和 chunk_index 有什么用？**
> 答：检索结果靠这对 key 定位原始文件和块位置；RRF 融合也用它做去重键。没有它，结果无法追溯到源码。

---

## 4.2 dense_retriever.py — 稠密向量检索

### 完整代码

```python
"""Dense 检索器：封装 Chroma 的检索、添加、删除操作"""

import os
import json
from threading import Lock
from pathlib import Path
from typing import Any

from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
import chromadb

from app.clients import get_redis_client
from app.config import settings
from app.logger import log

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent

# 检索范围常量：系统语料 / 用户上传
SYSTEM_CORPUS = {"source_type": "system"}
USER_CORPUS = {"source_type": "user_upload"}
SYSTEM_COLLECTION = "system_code"
USER_UPLOAD_COLLECTION = "user_uploads"

_embedding_models: dict[tuple[str, str], HuggingFaceEmbeddings] = {}
_embedding_models_lock = Lock()
_chroma_clients: dict[str, chromadb.PersistentClient] = {}
_chroma_clients_lock = Lock()


def get_embeddings() -> HuggingFaceEmbeddings:
    """Load each embedding model once per backend process."""
    key = (settings.EMBEDDING_MODEL, settings.EMBEDDING_DEVICE)
    with _embedding_models_lock:
        embeddings = _embedding_models.get(key)
        if embeddings is None:
            log.info("Loading embedding model: %s", settings.EMBEDDING_MODEL)
            embeddings = HuggingFaceEmbeddings(
                model_name=settings.EMBEDDING_MODEL,
                model_kwargs={"device": settings.EMBEDDING_DEVICE},
            )
            _embedding_models[key] = embeddings
        return embeddings


def get_chroma_client(persist_dir: str) -> chromadb.PersistentClient:
    """Reuse one Chroma persistent client for each on-disk database."""
    path = str(Path(persist_dir).resolve())
    with _chroma_clients_lock:
        client = _chroma_clients.get(path)
        if client is None:
            client = chromadb.PersistentClient(path=path)
            _chroma_clients[path] = client
        return client


class DenseRetriever:
    """基于 Chroma 的稠密向量检索器"""

    def __init__(self, collection_name: str = SYSTEM_COLLECTION):
        self.collection_name = collection_name
        chroma_path = settings.CHROMA_PERSIST_DIR
        if not os.path.isabs(chroma_path):
            chroma_path = str(PROJECT_ROOT / chroma_path)
        self.persist_dir = chroma_path

        os.makedirs(self.persist_dir, exist_ok=True)

        try:
            self.embeddings = get_embeddings()
        except Exception as e:
            raise RuntimeError(
                f"Failed to load embedding model '{settings.EMBEDDING_MODEL}': {e}"
            )

        self.redis_client = get_redis_client()

        try:
            self.db = Chroma(
                collection_name=self.collection_name,
                persist_directory=self.persist_dir,
                embedding_function=self.embeddings,
                client=get_chroma_client(self.persist_dir),
            )
        except Exception as e:
            raise RuntimeError(f"Failed to initialize Chroma at {self.persist_dir}: {e}")

    def search(self, query: str, k: int = 5,
               where: dict | None = None) -> list[dict[str, Any]]:
        """稠密检索。where 是 Chroma metadata filter，用于隔离检索范围。

        示例：
          search("query")                          # 搜全部（默认）
          search("query", where={"source_type": "system"})
          search("query", where={"owner_id": 1, "source_type": "user_upload"})
        """
        if not query or not query.strip():
            return []

        where_str = json.dumps(where, sort_keys=True) if where else "all"
        cache_key = f"dense_search:{self.collection_name}:{query.strip()}:{k}:{where_str}"
        if self.redis_client:
            try:
                cached = self.redis_client.get(cache_key)
                if cached:
                    return json.loads(cached)
            except Exception:
                pass

        try:
            if where:
                docs = self.db.similarity_search(query, k=k, filter=where)
            else:
                docs = self.db.similarity_search(query, k=k)
        except Exception as e:
            log.error("Search failed: %s", e)
            return []

        results = [
            {
                "text": doc.page_content,
                "source": doc.metadata.get("source", "unknown"),
                "chunk_index": doc.metadata.get("chunk_index", -1),
                "owner_id": doc.metadata.get("owner_id"),
                "score": None,
            }
            for doc in docs
        ]

        if self.redis_client and results:
            try:
                self.redis_client.setex(
                    cache_key, settings.REDIS_CACHE_TTL,
                    json.dumps(results, ensure_ascii=False),
                )
            except Exception:
                pass

        return results

    def search_with_score(self, query: str, k: int = 5,
                          where: dict | None = None) -> list[dict[str, Any]]:
        if not query or not query.strip():
            return []

        where_str = json.dumps(where, sort_keys=True) if where else "all"
        cache_key = f"dense_search_score:{self.collection_name}:{query.strip()}:{k}:{where_str}"
        if self.redis_client:
            try:
                cached = self.redis_client.get(cache_key)
                if cached:
                    return json.loads(cached)
            except Exception:
                pass

        try:
            if where:
                docs_with_scores = self.db.similarity_search_with_score(query, k=k, filter=where)
            else:
                docs_with_scores = self.db.similarity_search_with_score(query, k=k)
        except Exception as e:
            log.error("Search with score failed: %s", e)
            return []

        results = [
            {
                "text": doc.page_content,
                "source": doc.metadata.get("source", "unknown"),
                "chunk_index": doc.metadata.get("chunk_index", -1),
                "owner_id": doc.metadata.get("owner_id"),
                "score": score,
            }
            for doc, score in docs_with_scores
        ]

        if self.redis_client and results:
            try:
                self.redis_client.setex(
                    cache_key, settings.REDIS_CACHE_TTL,
                    json.dumps(results, ensure_ascii=False),
                )
            except Exception:
                pass

        return results

    def add_chunks(self, chunks: list[dict[str, Any]]) -> list[str]:
        if not chunks:
            log.warning("No chunks to add")
            return []

        texts = [c["text"] for c in chunks]
        metadatas = [c["metadata"] for c in chunks]

        try:
            ids = self.db.add_texts(texts=texts, metadatas=metadatas)
            self._clear_cache()
            return ids
        except Exception as e:
            log.error("Failed to add chunks: %s", e)
            return []

    def replace_chunks(self, chunks: list[dict[str, Any]]) -> list[str]:
        """Replace a collection while restoring its prior contents on write failure."""
        if not chunks:
            raise ValueError("Cannot replace a collection with no chunks")

        old_documents = []
        old_metadatas = []
        old_ids = []
        try:
            previous = self.db.get(include=["documents", "metadatas"])
            old_documents = previous.get("documents") or []
            old_metadatas = previous.get("metadatas") or []
            old_ids = previous.get("ids") or []
            self.db.delete_collection()
            self.db = Chroma(
                collection_name=self.collection_name,
                persist_directory=self.persist_dir,
                embedding_function=self.embeddings,
                client=get_chroma_client(self.persist_dir),
            )
            ids = self.add_chunks(chunks)
            if len(ids) != len(chunks):
                raise RuntimeError("Chroma did not store every new chunk")
            return ids
        except Exception as exc:
            log.error("Collection replacement failed: %s", exc)
            try:
                self.db.delete_collection()
                self.db = Chroma(
                    collection_name=self.collection_name,
                    persist_directory=self.persist_dir,
                    embedding_function=self.embeddings,
                    client=get_chroma_client(self.persist_dir),
                )
                if old_documents:
                    self.db.add_texts(
                        texts=old_documents,
                        metadatas=old_metadatas,
                        ids=old_ids,
                    )
                log.warning("Restored previous collection after failed replacement")
            except Exception:
                log.exception("Failed to restore the previous collection")
            raise RuntimeError("Failed to replace collection") from exc

    def count(self) -> int:
        try:
            return self.db._collection.count()
        except Exception as e:
            log.error("Failed to get count: %s", e)
            return 0

    def delete_collection(self):
        try:
            self.db.delete_collection()
            self._clear_cache()
            log.info("Collection deleted")
        except Exception as e:
            log.warning("Delete failed (may not exist): %s", e)

    def _clear_cache(self):
        """清除当前 collection 的检索缓存，避免重建后命中旧结果。"""
        if not self.redis_client:
            return

        try:
            keys = list(self.redis_client.scan_iter(f"dense_search:{self.collection_name}:*"))
            if keys:
                self.redis_client.delete(*keys)
        except Exception as e:
            log.warning("Failed to clear search cache: %s", e)
```

### 这段代码解决什么问题

稠密检索 = 把文本和查询都转成**向量**，算**语义相似度**。这是 RAG 的"语义路"。实现上封装 Chroma（向量数据库）+ `all-MiniLM-L6-v2`（嵌入模型）。

**它和 BM25 的本质区别**：BM25 是"字面匹配"（搜 "store" 必须出现 "store"），稠密检索是"语义匹配"（搜 "怎么保存数据" 能匹配到 `storages.py`，因为语义相近）。

### 关键代码逐句拆解

**① 检索范围常量 — 数据隔离的基石**

```python
SYSTEM_CORPUS = {"source_type": "system"}
USER_CORPUS = {"source_type": "user_upload"}
SYSTEM_COLLECTION = "system_code"
USER_UPLOAD_COLLECTION = "user_uploads"
```

系统语料（TinyDB 源码）和用户上传内容在**检索端**就区分开。这就是 Chroma 的 metadata filter 条件。**除了 metadata filter，还引入了物理隔离**：`SYSTEM_COLLECTION` / `USER_UPLOAD_COLLECTION` 是两个独立的 Chroma collection，系统重建索引时只删 `system_code`，不会触碰 `user_uploads`。

**② 构造函数的 collection 参数**

```python
def __init__(self, collection_name: str = SYSTEM_COLLECTION):
    self.collection_name = collection_name
    ...
    self.db = Chroma(
        collection_name=self.collection_name,
        persist_directory=self.persist_dir,
        embedding_function=self.embeddings,
    )
```

现在 `DenseRetriever` 可以指定操作哪个 collection。系统代码检索用 `system_code`，project 知识库用 `project_code`（见 knowledge_bases.py），用户上传用 `user_uploads`。

Redis 连接也加了 **`socket_connect_timeout=0.2` / `socket_timeout=0.2` / `retry=Retry(NoBackoff(), retries=0)`**——短超时 + 不重试，避免 Redis 挂掉时请求卡住几秒。

**③ `PROJECT_ROOT` 计算**

```python
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
```

`__file__` 在 `backend/app/rag/dense_retriever.py`，往上推 4 层 = 项目根目录。比 config.py 的 `parents[2]` 多 2 层，因为目录层级更深。用于定位相对路径的 `CHROMA_PERSIST_DIR`。

**④ 缓存 key 的构造 — 缓存命中的关键**

```python
where_str = json.dumps(where, sort_keys=True) if where else "all"
cache_key = f"dense_search:{self.collection_name}:{query.strip()}:{k}:{where_str}"
```

`sort_keys=True` 保证 `{"a":1,"b":2}` 和 `{"b":2,"a":1}` 生成**同一个** key——dict 顺序不影响缓存命中。**注意 key 里带了 `collection_name`**——不同 collection 的检索结果不会互相污染缓存。

**⑤ 缓存读写的降级**

```python
if self.redis_client:
    try:
        cached = self.redis_client.get(cache_key)
        if cached:
            return json.loads(cached)
    except Exception:
        pass
```

- 查缓存命中就直接返回，省掉一次昂贵的向量检索。
- **Redis 不可用时静默跳过**（`except: pass`），检索照常走，只是没有缓存。
- `json.loads(cached)` 把缓存 JSON 还原成结果列表。

写缓存同理：`setex(cache_key, settings.REDIS_CACHE_TTL, json.dumps(results, ensure_ascii=False))`。`ensure_ascii=False` 防止中文被转义成 `\uXXXX`，省空间、可读。

**⑥ 统一结果结构**

```python
results = [
    {
        "text": doc.page_content,
        "source": doc.metadata.get("source", "unknown"),
        "chunk_index": doc.metadata.get("chunk_index", -1),
        "owner_id": doc.metadata.get("owner_id"),
        "score": None,
    }
    for doc in docs
]
```

注意 **`"score": None`**——稠密检索本身不返回相关性分数（Chroma 的 `similarity_search` 不附带分数）。这恰恰是 RRF 融合的**设计前提**：RRF 只看排名不看分数。如果需要分数，用 `search_with_score`（底层 `similarity_search_with_score`）。

`metadata.get(...)` 用 `.get` + 默认值，保证即使某个 chunk 缺字段也不崩。

**⑦ `add_chunks` / `delete_collection` — 写索引 + 清缓存**

```python
def add_chunks(self, chunks):
    ...
    ids = self.db.add_texts(texts=texts, metadatas=metadatas)
    self._clear_cache()   # ← 新增：写入后清缓存
    return ids

def delete_collection(self):
    self.db.delete_collection()
    self._clear_cache()   # ← 新增：删除后清缓存

def _clear_cache(self):
    keys = list(self.redis_client.scan_iter(f"dense_search:{self.collection_name}:*"))
    if keys:
        self.redis_client.delete(*keys)
```

**这是一个重要的 bug 修复**：原来重建索引（删除 + 重新 add）后，Redis 里可能还留着**旧索引的缓存**，导致检索命中过期结果。`_clear_cache` 用 `scan_iter` 扫出当前 collection 的所有缓存 key 并删除——保证重建后第一次检索是真实的，不会命中旧数据。

批量写入。`metadatas` 里带 `source` / `chunk_index` / `source_type` / `owner_id`——这些就是后续 filter 检索的条件。

### 面试答题要点

> **Q：稠密检索和稀疏检索的区别？**
> 答：稠密检索把文本/查询都编码成向量，用余弦相似度算语义相似——懂同义词、能匹配语义相近但字面不同的内容；稀疏检索（BM25）是词频统计，精确匹配关键词但对同义词无能为力。两者互补。

> **Q：为什么稠密检索结果不带分数也能融合？**
> 答：因为融合用的是 RRF——只看排名不看分数。稠密路的向量距离和 BM25 的词频分数度量衡不同，直接比较无意义；RRF 按排名给分规避了这个问题。

> **Q：检索结果缓存怎么做？**
> 答：以 `collection + query + k + where` 序列化做 key 存 Redis，TTL 5 分钟。`json.dumps(where, sort_keys=True)` 保证 dict 顺序不影响 key。Redis 挂了自动降级跳过缓存。

> **Q：系统索引和用户上传怎么隔离？**
> 答：两层。**物理层**：`system_code` 和 `user_uploads` 是两个独立 Chroma collection，重建系统索引只删 `system_code`，不碰用户数据；**逻辑层**：检索时 metadata filter 按 `source_type` / `owner_id` 过滤。物理 + 逻辑双重隔离。

> **Q：嵌入模型选型？**
> 答：默认 `all-MiniLM-L6-v2`（轻量 ~23MB、快、英文好）。代码里也留了中文模型的备选（bge-small-zh-v1.5）。**关键考量**：本项目是"中文查询 + 英文代码"的跨语言检索场景，而 all-MiniLM 是纯英文模型，对中文查询的向量表达很弱。理论上中英双语的 bge-small-zh-v1.5 可能更合适，但**具体哪个更好需要实测验证**——用 RAGAS 跑同一测试集对比两种 embedding 的分数，记录题集版本、索引版本、Judge 模型和运行日期后再下结论（见 4.12 节）。这再次说明"组件要按领域实测验证"。

---

## 4.2 knowledge_bases.py — 多知识库定义

### 完整代码

```python
"""Static definitions for the public code knowledge bases."""

from dataclasses import dataclass

from app.config import PROJECT_ROOT, settings


@dataclass(frozen=True)
class KnowledgeBase:
    id: str
    label: str
    collection_name: str
    repo_path: str


TINYDB_KNOWLEDGE_BASE = "tinydb"
PROJECT_KNOWLEDGE_BASE = "project"
DEFAULT_KNOWLEDGE_BASE = TINYDB_KNOWLEDGE_BASE

KNOWLEDGE_BASES = {
    TINYDB_KNOWLEDGE_BASE: KnowledgeBase(
        id=TINYDB_KNOWLEDGE_BASE,
        label="TinyDB",
        collection_name="system_code",
        repo_path=settings.REPO_PATH,
    ),
    PROJECT_KNOWLEDGE_BASE: KnowledgeBase(
        id=PROJECT_KNOWLEDGE_BASE,
        label="Code Assistant Agent",
        collection_name="project_code",
        repo_path=settings.PROJECT_SOURCE_PATH or str(PROJECT_ROOT),
    ),
}


def get_knowledge_base(knowledge_base_id: str) -> KnowledgeBase:
    try:
        return KNOWLEDGE_BASES[knowledge_base_id]
    except KeyError as exc:
        raise ValueError(f"Unknown knowledge base '{knowledge_base_id}'") from exc
```

### 这段代码解决什么问题

把"有哪些可检索的知识库"**集中定义成一张表**。每个知识库有四个属性：

- `id`：唯一标识（`tinydb` / `project`），API 请求用它指定。
- `label`：人类可读名，用于前端下拉框、Agent 提示词。
- `collection_name`：对应的 Chroma collection（`system_code` / `project_code`）。
- `repo_path`：源码目录，索引时从这读代码。

### 关键代码逐句拆解

**① `@dataclass(frozen=True)`**

```python
@dataclass(frozen=True)
class KnowledgeBase:
```

`dataclass` 自动生成 `__init__` / `__repr__` / `__eq__`，少写样板代码。**`frozen=True` 让实例不可变**——知识库是静态定义，创建后不允许改，防止运行时被意外篡改。

**② 默认知识库**

```python
DEFAULT_KNOWLEDGE_BASE = TINYDB_KNOWLEDGE_BASE
```

默认 `tinydb`。这样没指定知识库的调用（Agent 工具、旧请求）自动走 TinyDB。**提醒**：`tinydb` 作为默认值只是代码配置；实际能否检索取决于 `backend/data/target_repo` 下是否有 TinyDB 源码（当前本机缺失时该知识库构建会返回 `skipped`）。当前完整可演示的知识库是 `project`。

**③ `get_knowledge_base` — 带错误信息的查找**

```python
def get_knowledge_base(knowledge_base_id: str) -> KnowledgeBase:
    try:
        return KNOWLEDGE_BASES[knowledge_base_id]
    except KeyError as exc:
        raise ValueError(f"Unknown knowledge base '{knowledge_base_id}'") from exc
```

未知知识库 ID 抛 `ValueError`（比裸 `KeyError` 更友好），`from exc` 保留原始异常链。

**④ 多知识库如何贯通全项目**

- `code_indexer.create_index(knowledge_base_id)`：按知识库建索引。
- `DenseRetriever(collection_name=kb.collection_name)`：按知识库选 collection。
- `SparseRetriever.from_redis(kb.collection_name)`：按知识库恢复 BM25。
- `AgentHarness(knowledge_base_id=...)`：Agent 绑定知识库，工具描述自动带知识库名。
- `/api/search`、`/api/agent/chat` 都接受 `knowledge_base` 参数。

### 面试答题要点

> **Q：多知识库怎么实现的？**
> 答：用一个 dataclass 定义知识库的元信息（id / label / collection_name / repo_path），集中管理。检索器、索引器、Agent 都从知识库取 collection_name，按需切换。新增知识库只需在 `KNOWLEDGE_BASES` 加一条，各模块自动适配。

> **Q：为什么用 frozen dataclass？**
> 答：知识库是静态配置，运行时不应被修改。frozen=True 让实例不可变，避免意外篡改导致的检索错乱。

---

## 4.4 sparse_retriever.py — BM25 稀疏检索

### 完整代码

```python
"""Sparse 检索器：基于 BM25 的关键词检索"""

import re
import json

from rank_bm25 import BM25Okapi

from app.clients import get_redis_client
from app.config import settings
from app.logger import log


class SparseRetriever:
    """基于 BM25 的稀疏检索器"""

    def __init__(self, collection_name: str = "system_code"):
        self.collection_name = collection_name
        self.bm25 = None
        self.chunks: list[dict] = []
        self._tokenized: list[list[str]] = []

        self.redis_client = get_redis_client()

    def _tokenize(self, text: str) -> list[str]:
        tokens = re.findall(r"[a-zA-Z_]\w*", text.lower())
        return [t for t in tokens if len(t) > 1]

    def build_index(self, chunks: list[dict]):
        self.chunks = chunks
        self._tokenized = [self._tokenize(c["text"]) for c in chunks]
        self.bm25 = BM25Okapi(self._tokenized)
        self._save_to_redis()
        log.info("Index built with %d chunks", len(chunks))

    def search(self, query: str, k: int = 5) -> list[dict]:
        if not query or not query.strip() or not self.bm25:
            return []

        tokenized_query = self._tokenize(query)
        if not tokenized_query:
            return []

        scores = self.bm25.get_scores(tokenized_query)
        top_n_indices = sorted(
            range(len(scores)), key=lambda i: scores[i], reverse=True
        )[:k]

        results = []
        for idx in top_n_indices:
            if scores[idx] > 0:
                results.append({
                    "text": self.chunks[idx]["text"],
                    "source": self.chunks[idx]["metadata"]["source"],
                    "chunk_index": self.chunks[idx]["metadata"]["chunk_index"],
                    "score": float(scores[idx]),
                })
        return results

    def count(self) -> int:
        return len(self.chunks) if self.bm25 else 0

    def redis_key(self) -> str:
        return f"bm25_index:{self.collection_name}:{settings.CHUNK_STRATEGY}"

    def _save_to_redis(self):
        if not self.redis_client or not self.bm25:
            return
        try:
            data = {
                "chunks": self.chunks,
                "corpus": self._tokenized,
            }
            self.redis_client.setex(
                self.redis_key(), 3600 * 24,
                json.dumps(data, ensure_ascii=False, default=str),
            )
        except Exception as e:
            log.warning("Failed to cache to Redis: %s", e)

    @classmethod
    def from_redis(cls, collection_name: str = "system_code") -> "SparseRetriever":
        retriever = cls(collection_name=collection_name)
        if not retriever.redis_client:
            return retriever
        try:
            data = retriever.redis_client.get(retriever.redis_key())
            if data:
                parsed = json.loads(data)
                retriever.chunks = parsed["chunks"]
                retriever._tokenized = parsed["corpus"]
                retriever.bm25 = BM25Okapi(retriever._tokenized)
                log.info("Restored from Redis (%d chunks)", len(retriever.chunks))
        except Exception as e:
            log.warning("Redis restore failed: %s", e)
        return retriever

    @classmethod
    def from_chunks(
        cls, chunks: list[dict], collection_name: str = "system_code",
    ) -> "SparseRetriever":
        retriever = cls(collection_name=collection_name)
        retriever.build_index(chunks)
        return retriever
```

### 这段代码解决什么问题

BM25 是信息检索的经典算法（Okapi BM25），属于**稀疏检索**：基于词频统计，算"查询词在文档里有多重要"。和稠密检索互补——它对**专有名词、函数名、标识符**（如 `JSONStorage`、`insert`）非常精准，而这些恰恰是代码检索最常见的查询。

### 关键代码逐句拆解

**① 分词 — 代码检索的关键**

```python
def _tokenize(self, text: str) -> list[str]:
    tokens = re.findall(r"[a-zA-Z_]\w*", text.lower())
    return [t for t in tokens if len(t) > 1]
```

正则 `[a-zA-Z_]\w*` 匹配 Python 标识符（变量名、函数名、类名），`lower()` 统一小写，过滤单字符。这样 `insert`、`table`、`query` 等 token 能精确匹配代码里的词。

**② `build_index` — 建 BM25 索引**

```python
def build_index(self, chunks: list[dict]):
    self.chunks = chunks
    self._tokenized = [self._tokenize(c["text"]) for c in chunks]
    self.bm25 = BM25Okapi(self._tokenized)
    self._save_to_redis()
```

把所有 chunk 分词，`BM25Okapi` 根据语料构建倒排统计。`rank_bm25` 库一行搞定。

**③ `search` — 检索**

```python
scores = self.bm25.get_scores(tokenized_query)
top_n_indices = sorted(
    range(len(scores)), key=lambda i: scores[i], reverse=True
)[:k]
```

`get_scores` 返回所有 chunk 的 BM25 分数，按分数排序取前 k 个索引，然后**过滤掉分数为 0 的**（`if scores[idx] > 0`——完全没匹配到任何查询词的结果没意义）。

注意返回结构里 `"score": float(scores[idx])`——**BM25 路是有真实分数的**，与稠密路的 `score: None` 形成对比，更凸显 RRF"只看排名"的价值。

**④ 索引持久化到 Redis — 亮点**

```python
def redis_key(self) -> str:
    return f"bm25_index:{self.collection_name}:{settings.CHUNK_STRATEGY}"

def _save_to_redis(self):
    data = {"chunks": self.chunks, "corpus": self._tokenized}
    self.redis_client.setex(self.redis_key(), 3600 * 24, json.dumps(data, ensure_ascii=False, default=str))

@classmethod
def from_redis(cls, collection_name: str = "system_code") -> "SparseRetriever":
    retriever = cls(collection_name=collection_name)
    data = retriever.redis_client.get(retriever.redis_key())
    if data:
        parsed = json.loads(data)
        retriever.chunks = parsed["chunks"]
        retriever._tokenized = parsed["corpus"]
        retriever.bm25 = BM25Okapi(retriever._tokenized)
    return retriever
```

**为什么 BM25 索引要缓存到 Redis？** BM25 索引在内存里，服务重启就没了。重建要重新读几百个 chunk 并分词（耗时）。缓存到 Redis 后，服务重启直接 `from_redis()` 恢复，秒级启动。

**`redis_key` 带 `collection_name` + `CHUNK_STRATEGY`**：不同知识库（tinydb 的 `system_code`、project 的 `project_code`）的 BM25 索引互不污染，分块策略变了 key 也变。`from_redis()` / `from_chunks()` 是**类方法工厂**，两种构建方式：从 Redis 恢复、或从 chunks 现建。

`default=str`：JSON 序列化时兜底处理不可序列化的对象（比如某些 datetime）。

### 面试答题要点

> **Q：BM25 是什么？和 TF-IDF 什么区别？**
> 答：BM25 是 TF-IDF 的改进版。它加了文档长度归一化（短文档中的词匹配更值钱）和饱和函数（词频过高时得分不线性增长）。`rank_bm25` 的 `BM25Okapi` 实现了这个算法。

> **Q：为什么 BM25 索引要存 Redis？**
> 答：BM25 是内存索引，进程重启就丢。存 Redis 让新进程秒级恢复，不用重新分词几百个 chunk。key 带 collection 名 + 分块策略名，防止不同知识库、不同配置的索引互相污染。

> **Q：分词怎么针对代码设计？**
> 答：用 `[a-zA-Z_]\w*` 正则只提取标识符（函数名、类名、变量名），过滤单字符。这样 `insert`、`JSONStorage` 等代码元素能精确参与 BM25 词频统计，比通用英文分词更适合代码检索。

> **Q：稀疏检索的局限？**
> 答：不懂同义词和语义（搜"保存数据"匹配不到 `storages.py` 里的 `write`）；对大小写、拼写敏感。所以需要稠密检索互补。

---

## 4.5 fusion.py — RRF 结果融合

### 完整代码

```python
"""结果融合：RRF (Reciprocal Rank Fusion) 合并多路检索结果"""

import asyncio
import time
from typing import Any

from app.logger import log


def rrf(
    results_list: list[list[dict[str, Any]]],
    k: int = 60,
    top_n: int = 5,
) -> list[dict[str, Any]]:
    fusion_scores: dict[tuple[str, int], dict] = {}

    for results in results_list:
        for rank, item in enumerate(results):
            key = (item["source"], item["chunk_index"])
            if key not in fusion_scores:
                fusion_scores[key] = {
                    "text": item["text"],
                    "source": item["source"],
                    "chunk_index": item["chunk_index"],
                    "score": 0.0,
                }
            fusion_scores[key]["score"] += 1.0 / (k + rank + 1)

    sorted_items = sorted(
        fusion_scores.values(),
        key=lambda x: x["score"],
        reverse=True,
    )
    return sorted_items[:top_n]


def hybrid_search(
    query: str,
    dense_retriever,
    sparse_retriever,
    k_dense: int = 10,
    k_sparse: int = 10,
    k_rrf: int = 60,
    top_n: int = 5,
    dense_where: dict | None = None,
) -> dict:
    start = time.time()

    dense_results = dense_retriever.search(query, k=k_dense, where=dense_where)
    sparse_results = sparse_retriever.search(query, k=k_sparse)

    log.info("Dense: %d results, Sparse: %d results", len(dense_results), len(sparse_results))

    fused = rrf([dense_results, sparse_results], k=k_rrf, top_n=top_n)

    total_ms = round((time.time() - start) * 1000, 2)
    log.info("Fused: %d, latency: %.2fms", len(fused), total_ms)

    return {
        "results": fused,
        "dense_top_k": dense_results[:3],
        "sparse_top_k": sparse_results[:3],
        "latency_ms": total_ms,
    }


async def async_hybrid_search(
    query: str,
    dense_retriever,
    sparse_retriever,
    k_dense: int = 10,
    k_sparse: int = 10,
    k_rrf: int = 60,
    top_n: int = 5,
    dense_where: dict | None = None,
) -> list[dict[str, Any]]:
    """异步混合检索：用 to_thread 避免阻塞事件循环"""
    result = await asyncio.to_thread(
        hybrid_search,
        query, dense_retriever, sparse_retriever,
        k_dense=k_dense, k_sparse=k_sparse,
        k_rrf=k_rrf, top_n=top_n,
        dense_where=dense_where,
    )

    try:
        from app.database import async_session_factory
        from app.models.retrieval_log import RetrievalLog
        import datetime
        from datetime import UTC

        async with async_session_factory() as session:
            session.add(RetrievalLog(
                query_text=query,
                dense_top_k=result["dense_top_k"],
                sparse_top_k=result["sparse_top_k"],
                fused_top_n=result["results"],
                strategy="hybrid",
                total_latency_ms=result["latency_ms"],
            ))
            await session.commit()
    except Exception as e:
        log.warning("Failed to log retrieval: %s", e)

    return result["results"]
```

### 这段代码解决什么问题

两路检索各自返回 top-k，**怎么合并成一路？** 直接加权平均不行——两路分数度量衡完全不同。**RRF（Reciprocal Rank Fusion）** 是标准解法：只看排名，不碰分数。

### 关键代码逐句拆解

**① RRF 核心公式**

```python
def rrf(results_list, k=60, top_n=5):
    fusion_scores = {}
    for results in results_list:
        for rank, item in enumerate(results):
            key = (item["source"], item["chunk_index"])
            if key not in fusion_scores:
                fusion_scores[key] = {...}
            fusion_scores[key]["score"] += 1.0 / (k + rank + 1)
```

公式是 `score = Σ 1/(k + rank)`：

- 一个文档在**每一路**里都有一个排名（rank 从 0 开始）。
- 每路的贡献是 `1/(60 + rank + 1)`。
- 排名越靠前，贡献越大；跨路累加。

**关键**：它只用 `rank`（排名），从不看原分数。稠密路返回 0.9 分和 BM25 返回 1000 分，都只按"排第几"算贡献——这就是为什么前面说"分数不可比也能融合"。

**去重键 `(source, chunk_index)`**：同一个 chunk 被两路都召回时，`fusion_scores` 里只有一个 key，分数累加。**被两路同时召回的 chunk 会获得双倍贡献，自然排到前面**——这是 RRF 的另一个妙处：两路都认为重要的，大概率真的重要。

**② `hybrid_search` — 同步编排**

```python
dense_results = dense_retriever.search(query, k=k_dense, where=dense_where)
sparse_results = sparse_retriever.search(query, k=k_sparse)
fused = rrf([dense_results, sparse_results], k=k_rrf, top_n=top_n)
```

双路各取 top-10 → RRF 融合 top-5 → 记录延迟。

返回值是**结构化字典**：

```python
return {
    "results": fused,            # 融合后的最终结果
    "dense_top_k": dense_results[:3],   # 稠密路 top-3（用于日志）
    "sparse_top_k": sparse_results[:3], # 稀疏路 top-3（用于日志）
    "latency_ms": total_ms,       # 总耗时
}
```

`dense_top_k` / `sparse_top_k` 是**给日志用的**——你可以对比两路各自搜到什么，融合后剩下什么。

**③ `async_hybrid_search` — 异步版 + 链路日志**

```python
result = await asyncio.to_thread(
    hybrid_search, query, dense_retriever, sparse_retriever, ...
)
```

`hybrid_search` 是同步函数（里面 Chroma / BM25 都是同步库）。**直接 await 会阻塞事件循环**，所以用 `asyncio.to_thread` 把它扔到线程池跑，不阻塞其他请求。这是"同步阻塞库嵌进异步框架"的标准解法。

然后异步写 `RetrievalLog`（第 2 层的 `retrieval_logs` 表）——把三路中间结果 + 延迟落库。`try/except` 包住：**日志失败不影响检索主流程**。

### 面试答题要点

> **Q：为什么用 RRF 而不是加权平均？**
> 答：稠密检索的分数（向量距离）和 BM25 的分数（词频统计）度量衡完全不同，直接加权没有意义。RRF 只看排名不看分数，规避了分数不可比的问题，是信息检索的标准做法。

> **Q：RRF 公式里的 k 有什么用？**
> 答：k 是平滑常数（常用 60）。防止排名第 1 的文档分数过高，让排名差异不要被过分放大。`1/(60+1)` vs `1/(60+2)` 差距很小，而 `1/1` vs `1/2` 差距巨大——k 让融合更"温和"。

> **Q：同一个文档在两路都被召回会怎样？**
> 答：`(source, chunk_index)` 作为去重键，两路贡献累加，它会被推到更靠前的位置。这是 RRF 的隐性优势：两路都认为重要的文档优先。

> **Q：为什么用 asyncio.to_thread？**
> 答：Chroma 和 BM25 是同步库，直接 await 会阻塞 FastAPI 的事件循环。to_thread 把它们扔到线程池，让出事件循环处理其他请求。

> **Q：检索日志为什么要存三路结果？**
> 答：可观测性。回看任何一次检索，能对比稠密路/稀疏路各自召回什么、融合后剩什么、耗时多少。排查"某次检索为什么不好"时有现场录像。

---

## 4.6 query_rewriter.py — HyDE 查询改写

### 完整代码

```python
"""查询改写：HyDE (Hypothetical Document Embedding) 策略"""

import asyncio

from app.agent.llm import call_llm
from app.logger import log

HYDE_SYSTEM_PROMPT = """你是一个 Python 代码助手。用户会问一个关于代码库的问题。
请生成一段你认为最能回答这个问题的 Python 代码片段。
只需要输出代码，不要解释。如果问题不涉及代码，用伪代码表示。"""

EXPAND_SYSTEM_PROMPT = """你是一个搜索优化助手。用户输入一个简短的搜索查询。
请将其扩展为 2-3 个更具体、更可能匹配到相关代码的搜索词。
直接用逗号分隔输出，不要多余解释。"""


async def _save_rewrite_record(original: str, rewritten: str, strategy: str):
    """异步写入 query_rewrites 表（即发即忘，不阻塞调用方）"""
    try:
        from app.database import async_session_factory
        from app.models.query_rewrite import QueryRewrite

        async with async_session_factory() as session:
            session.add(QueryRewrite(
                original_query=original,
                rewritten_query=rewritten,
                strategy=strategy,
            ))
            await session.commit()
    except Exception as e:
        log.warning("Failed to save rewrite record: %s", e)


def hyde_rewrite(query: str) -> str:
    log.info("HyDE rewriting: '%s'", query)
    hypothetical_code = call_llm(query, system_prompt=HYDE_SYSTEM_PROMPT)
    if hypothetical_code:
        log.info("HyDE result: %s...", hypothetical_code[:80])
        return hypothetical_code
    return query


def expand_query(query: str) -> str:
    log.info("Expanding query: '%s'", query)
    expanded = call_llm(query, system_prompt=EXPAND_SYSTEM_PROMPT)
    if expanded:
        log.info("Expanded: %s", expanded)
        return expanded
    return query


async def rewrite(query: str, strategy: str = "hyde") -> str:
    """
    统一的查询改写入口（异步，通过 to_thread 避免阻塞事件循环）

    缓存说明：
    - reranker 缓存键基于改写后的 query 文本，相同改写结果会命中缓存
    - 若要缓存"原始查询→改写结果"的映射，需调用方自行管理
    """
    # ① 将同步的 LLM 调用扔到线程池，不阻塞事件循环
    if strategy == "hyde":
        result = await asyncio.to_thread(hyde_rewrite, query)
    elif strategy == "expand":
        result = await asyncio.to_thread(expand_query, query)
    else:
        result = query

    # ② 粗细粒度的"是否改写"检测：去掉首尾空白后比较
    if result.strip() != query.strip() and result != query:
        asyncio.create_task(_save_rewrite_record(query, result, strategy))

    return result
```

### 这段代码解决什么问题

**用户问的自然语言问题和代码库里的真实代码，语义空间有差距。** 比如问"TinyDB 怎么把数据存到磁盘的？"，检索时拿这句话去匹配代码，效果一般。**HyDE（Hypothetical Document Embedding）** 的思路：先让 LLM 把问题"翻译"成一段假设性的代码，再拿这段代码去检索。

```
用户问题：TinyDB 怎么把数据存到磁盘的？
   │  LLM 生成假设代码
   ▼
with TinyDB('db.json') as db:
    db.insert({...})
   │  这段代码的向量和 storages.py 里的真实代码更接近
   ▼
检索命中 storages.py ✓
```

为什么有效？嵌入模型在"代码→代码"的空间里比对，比"自然语言→代码"准得多。这是业界常用的 RAG 优化手段。

### 关键代码逐句拆解

**① 两个系统提示词**

```python
HYDE_SYSTEM_PROMPT = """你是一个 Python 代码助手。... 请生成一段你认为最能回答这个问题的 Python 代码片段。
只需要输出代码，不要解释。"""

EXPAND_SYSTEM_PROMPT = """你是一个搜索优化助手。... 请将其扩展为 2-3 个更具体、更可能匹配到相关代码的搜索词。"""
```

两个策略：
- **hyde**：生成"假设代码"。
- **expand**：扩展成多个搜索词（更宽召回）。

**② `hyde_rewrite` / `expand_query` — 同步 LLM 调用**

```python
def hyde_rewrite(query: str) -> str:
    hypothetical_code = call_llm(query, system_prompt=HYDE_SYSTEM_PROMPT)
    if hypothetical_code:
        return hypothetical_code
    return query
```

`call_llm` 是第 5 层会讲到的 LLM 封装。**LLM 调用失败或返回空时，降级返回原查询**——改写失败不能让检索也失败。

**③ `rewrite` — 统一异步入口**

```python
if strategy == "hyde":
    result = await asyncio.to_thread(hyde_rewrite, query)
```

LLM 调用是同步阻塞的，用 `asyncio.to_thread` 扔线程池，不阻塞事件循环。

**④ 改写记录落库（即发即忘）**

```python
if result.strip() != query.strip() and result != query:
    asyncio.create_task(_save_rewrite_record(query, result, strategy))
```

两个条件判断"确实改写了"（去掉首尾空白后文本不同），然后 `asyncio.create_task` 异步写 `query_rewrites` 表——**不 await，即发即忘**，不拖慢检索响应。这与 fusion.py 里"日志失败不影响主流程"是同一哲学。

### 面试答题要点

> **Q：HyDE 的原理？**
> 答：检索前先让 LLM 根据问题生成一段假设文档（这里是假设代码），再用这段代码去检索。因为嵌入模型在"代码→代码"空间的相似度比对，比"自然语言→代码"更准，能提升召回率。

> **Q：HyDE 的代价？**
> 答：多一次 LLM 调用，延迟从不到 1ms 涨到约 3607ms（消融实验数据）。所以它要作为"可选开关"（search 接口的 `use_hyde` 参数），而不是默认开启。

> **Q：改写失败怎么办？**
> 答：LLM 调用失败或返回空，降级返回原查询——改写是锦上添花，不能让检索主干受影响。改写记录用 create_task 异步落库，不阻塞响应。

> **Q：消融实验里 HyDE 有没有提升？**
> 答：这个项目里没有（加了 HyDE 后 Hit Rate 保持 1.00 不变，MRR/NDCG 也几乎不变）。原因：基础混合检索已经够好，且测试集问题偏简单。代价是延迟从 0.89ms 飙到 3607ms，所以默认关闭。这正好说明"组件要按领域验证"——HyDE 在复杂、口语化查询下收益更大，这个项目的问题比较直白。

---

## 4.7 reranker.py — Cross-encoder 重排

### 完整代码

```python
"""Cross-encoder 重排序器：对初检结果精排（带 Redis 缓存）"""

import hashlib
import json

from sentence_transformers import CrossEncoder

from app.clients import get_redis_client
from app.config import settings
from app.logger import log


class Reranker:
    """基于 cross-encoder 的精排重排序"""

    def __init__(self):
        model_name = "cross-encoder/ms-marco-MiniLM-L-6-v2"
        log.info("Loading reranker: %s", model_name)
        try:
            self.model = CrossEncoder(model_name)
            log.info("Reranker loaded")
        except Exception as e:
            log.error("Failed to load reranker: %s", e)
            self.model = None

        self.redis_client = get_redis_client()

    def rerank(self, query: str, candidates: list[dict], top_n: int = 3) -> list[dict]:
        if not self.model or not candidates:
            for c in candidates:
                c["rerank_score"] = 0.0
            return candidates[:top_n]

        # 尝试从缓存读取（使用确定性哈希，跨进程一致）
        cache_key = f"rerank:{hashlib.md5(query.encode()).hexdigest()}:{top_n}"
        if self.redis_client:
            try:
                cached = self.redis_client.get(cache_key)
                if cached:
                    return json.loads(cached)
            except Exception:
                pass

        pairs = [(query, c["text"]) for c in candidates]
        scores = self.model.predict(pairs)

        for i, c in enumerate(candidates):
            c["rerank_score"] = float(scores[i])

        ranked = sorted(candidates, key=lambda x: x["rerank_score"], reverse=True)
        result = ranked[:top_n]

        log.info("Reranked %d candidates, top score: %.4f",
                 len(candidates), result[0]["rerank_score"] if result else 0)

        # 写入缓存
        if self.redis_client and result:
            try:
                self.redis_client.setex(
                    cache_key, 3600, json.dumps(result, ensure_ascii=False)
                )
            except Exception:
                pass

        return result

    def hybrid_search_with_rerank(
        self,
        query: str,
        dense_retriever,
        sparse_retriever,
        k_dense: int = 10,
        k_sparse: int = 10,
        k_rrf: int = 60,
        top_n: int = 3,
        dense_where: dict | None = None,
    ) -> list[dict]:
        from app.rag.fusion import hybrid_search

        result = hybrid_search(
            query, dense_retriever, sparse_retriever,
            k_dense=k_dense, k_sparse=k_sparse,
            k_rrf=k_rrf, top_n=top_n * 2,
            dense_where=dense_where,
        )

        return self.rerank(query, result["results"], top_n=top_n)
```

### 这段代码解决什么问题

**Cross-encoder 是"终极裁判"**：它把查询和文档**拼在一起**（`(query, doc)`）送进模型，一次只判断一对，输出匹配分数。这比稠密检索的 bi-encoder（各自编码、算余弦）**更精确**，但慢——所以只对初检的 top-N 精排，不做全库排序。

这是标准的"**召回粗排 + 精排**"两阶段架构：

```
全库 ——(稠密/BM25 双路召回，快)→ top-10 ——(cross-encoder 精排，慢但准)→ top-3
```

### 关键代码逐句拆解

**① 模型加载失败降级**

```python
try:
    self.model = CrossEncoder(model_name)
except Exception as e:
    log.error("Failed to load reranker: %s", e)
    self.model = None
```

模型加载失败（比如没下载、没显存）就置 `None`，后续 `rerank` 里 `if not self.model` 直接跳过精排，返回原结果——**重排是增强，不是主干，不能让它拖垮检索**。

**② 精排主体**

```python
pairs = [(query, c["text"]) for c in candidates]
scores = self.model.predict(pairs)

for i, c in enumerate(candidates):
    c["rerank_score"] = float(scores[i])

ranked = sorted(candidates, key=lambda x: x["rerank_score"], reverse=True)
result = ranked[:top_n]
```

构造 `(query, doc)` 对 → 模型预测分数 → 写回每个候选的 `rerank_score` → 按分数降序排序取 top_n。**注意它就地修改了 `candidates` 的 dict**（给每个加 `rerank_score` 字段），返回的是排序后的子集。

**③ 缓存 key — 确定性哈希**

```python
cache_key = f"rerank:{hashlib.md5(query.encode()).hexdigest()}:{top_n}"
```

用 `md5(query)` 做 key。**为什么用 md5 而不是直接拼 query？** 因为 query 可能很长、含特殊字符，直接拼进 Redis key 又长又丑。md5 保证：相同 query → 相同哈希（确定性，跨进程一致），key 长度固定 32 字符。`top_n` 也拼进去，因为不同 top_n 结果不同。

**④ `hybrid_search_with_rerank` — 一键组合**

```python
result = hybrid_search(
    query, dense_retriever, sparse_retriever,
    top_n=top_n * 2,      # 先召回 2 倍数量的候选
    ...
)
return self.rerank(query, result["results"], top_n=top_n)
```

先混合检索召回 `top_n * 2` 个候选，再精排到 `top_n`。**留出"余量"给精排挑**——如果初检只召回 3 个，精排没有选择空间。

### 面试答题要点

> **Q：bi-encoder 和 cross-encoder 的区别？**
> 答：bi-encoder 把查询和文档各自编码成向量，算相似度——快，可对全库预先索引，但精度有限；cross-encoder 把查询和文档拼接一起送进模型，直接输出匹配分——准，但慢（无法预索引）。所以架构上"bi-encoder/BM25 粗召回 + cross-encoder 精排"是标准组合。

> **Q：这个项目里 reranker 效果如何？**
> 答：消融实验显示**反而降分**（Hit Rate 从 1.00 → 0.85，MRR/NDCG 也从 0.59 → 0.49/0.48）。原因是 `ms-marco` 模型在网页搜索领域训练，对代码不敏感。这证明了"组件要按领域验证，不能无脑叠加"——是很诚实的工程结论。

> **Q：重排缓存怎么做？**
> 答：`md5(query)` + top_n 做 key 存 Redis 1 小时。md5 保证确定性哈希，相同查询跨进程一致，命中缓存省掉一次模型推理。

---

## 4.8 code_indexer.py — 离线索引编排器

### 完整代码

```python
"""代码索引编排器：读取文件 → chunker 分块 → dense_retriever 存储"""

import os
import glob
from threading import Lock
from time import perf_counter
from pathlib import Path

from app.config import settings
from app.rag.chunker import CodeChunker
from app.rag.dense_retriever import DenseRetriever
from app.rag.knowledge_bases import (
    DEFAULT_KNOWLEDGE_BASE,
    KNOWLEDGE_BASES,
    get_knowledge_base,
)
from app.rag.sparse_retriever import SparseRetriever
from app.database import async_session_factory
from app.models.index_version import IndexVersion
from app.logger import log

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
EXCLUDED_DIRECTORY_NAMES = {
    ".git", ".pytest_cache", ".venv", "env", "venv", "__pycache__", "data",
}
_rebuild_lock = Lock()


def load_code_files(repo_path: str) -> list[dict]:
    """读取 repo 下所有 .py 文件，返回 [{path, content}]"""
    documents = []
    full_path = repo_path
    if not os.path.isabs(repo_path):
        full_path = str(PROJECT_ROOT / repo_path)

    log.info("Looking for code in: %s", full_path)

    if not os.path.exists(full_path):
        log.error("Path does not exist: %s", full_path)
        return documents

    pattern = os.path.join(full_path, "**", "*.py")
    try:
        matched_files = glob.glob(pattern, recursive=True)
    except Exception as e:
        log.error("Failed to search files: %s", e)
        return documents

    for file_path in matched_files:
        relative_path = Path(os.path.relpath(file_path, full_path))
        if (
            "tests" in relative_path.parts
            or any(part in EXCLUDED_DIRECTORY_NAMES for part in relative_path.parts)
        ):
            continue
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
        except PermissionError:
            log.warning("Permission denied: %s", file_path)
            continue
        except UnicodeDecodeError:
            log.warning("Encoding error, trying latin-1: %s", file_path)
            try:
                with open(file_path, "r", encoding="latin-1") as f:
                    content = f.read()
            except Exception:
                continue
        except Exception as e:
            log.warning("Failed to read %s: %s", file_path, e)
            continue

        if content.strip():
            documents.append({
                "path": relative_path.as_posix(),
                "content": content,
            })
    return documents


async def save_version_record(strategy: str, chunk_size: int, chunk_overlap: int,
                              file_count: int, chunk_count: int,
                              build_duration_ms: int | None = None):
    """异步写入索引版本记录"""
    try:
        async with async_session_factory() as session:
            session.add(IndexVersion(
                strategy=strategy,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                file_count=file_count,
                chunk_count=chunk_count,
                build_duration_ms=build_duration_ms,
            ))
            await session.commit()
        log.info("Version record saved")
    except Exception as e:
        log.warning("Failed to save version record: %s", e)


async def create_index(knowledge_base_id: str = DEFAULT_KNOWLEDGE_BASE):
    """主流程：加载代码 → chunker 分块 → retriever 存储"""
    if not _rebuild_lock.acquire(blocking=False):
        return {"status": "busy", "knowledge_base": knowledge_base_id}

    started_at = perf_counter()
    try:
        knowledge_base = get_knowledge_base(knowledge_base_id)
        log.info("Loading %s code from %s", knowledge_base.id, knowledge_base.repo_path)
        documents = load_code_files(knowledge_base.repo_path)
        log.info("Loaded %d files", len(documents))
        if not documents:
            return {
                "status": "skipped",
                "knowledge_base": knowledge_base.id,
                "reason": "No indexable Python files found; existing index was kept",
            }

        chunker = CodeChunker(
            strategy=settings.CHUNK_STRATEGY,
            chunk_size=settings.CHUNK_SIZE,
            chunk_overlap=settings.CHUNK_OVERLAP,
        )
        chunks = chunker.chunk(documents)
        if not chunks:
            return {
                "status": "skipped",
                "knowledge_base": knowledge_base.id,
                "reason": "Chunking produced no content; existing index was kept",
            }
        log.info("Created %d chunks", len(chunks))

        for chunk in chunks:
            chunk["metadata"]["source_type"] = "system"
            chunk["metadata"]["knowledge_base"] = knowledge_base.id

        retriever = DenseRetriever(collection_name=knowledge_base.collection_name)
        retriever.replace_chunks(chunks)
        sparse = SparseRetriever.from_chunks(chunks, knowledge_base.collection_name)
        duration_ms = round((perf_counter() - started_at) * 1000)
        await save_version_record(
            strategy=settings.CHUNK_STRATEGY,
            chunk_size=settings.CHUNK_SIZE,
            chunk_overlap=settings.CHUNK_OVERLAP,
            file_count=len(documents),
            chunk_count=len(chunks),
            build_duration_ms=duration_ms,
        )
        log.info("Index %s built successfully with %d chunks", knowledge_base.id, len(chunks))
        return {
            "status": "ready",
            "knowledge_base": knowledge_base.id,
            "file_count": len(documents),
            "chunk_count": len(chunks),
            "duration_ms": duration_ms,
            "dense": retriever,
            "sparse": sparse,
        }
    except Exception as exc:
        log.exception("Failed to build index %s", knowledge_base_id)
        return {
            "status": "failed",
            "knowledge_base": knowledge_base_id,
            "reason": str(exc),
        }
    finally:
        _rebuild_lock.release()


async def rebuild_index(knowledge_base_id: str = DEFAULT_KNOWLEDGE_BASE):
    """对外暴露的"重建索引"接口，后续 API 路由会调用"""
    return await create_index(knowledge_base_id)


async def rebuild_all_indices():
    """Rebuild every public knowledge base without mixing their indexes."""
    results = {}
    for knowledge_base_id in KNOWLEDGE_BASES:
        results[knowledge_base_id] = await create_index(knowledge_base_id)
    return results


if __name__ == "__main__":
    import asyncio

    async def main():
        try:
            results = await rebuild_all_indices()
            for knowledge_base_id, result in results.items():
                print(f"{knowledge_base_id}: {result['status']}")
                if result.get("reason"):
                    print(f"  {result['reason']}")
        finally:
            from app.database import engine
            await engine.dispose()
            log.info("Database connections closed")

    asyncio.run(main())
```

### 这段代码解决什么问题

这是**离线建索引**的主流程（运行 `python -m app.rag.code_indexer` 触发）。把 TinyDB 源码变成可检索的稠密 + 稀疏双索引：

```
读取 .py 文件 ──► chunker 分块 ──► 打 system 标签
                                        │
                                        ├──► DenseRetriever.add_chunks → Chroma
                                        └──► SparseRetriever.from_chunks → BM25 + Redis
                                        └──► 写 index_versions 表
```

**为什么"离线"？** 因为建索引要加载嵌入模型、对全部代码做向量化，耗时以分钟计。不能每次请求都做——**一次建好，反复查询**。这和"查询时在线检索"是两回事。

### 关键代码逐句拆解

**① `load_code_files` — 递归读 .py 文件**

```python
pattern = os.path.join(full_path, "**", "*.py")
matched_files = glob.glob(pattern, recursive=True)
```

`glob` 递归匹配所有 `.py`。跳过清单：

```python
relative_path = Path(os.path.relpath(file_path, full_path))
if (
    "tests" in relative_path.parts
    or any(part in EXCLUDED_DIRECTORY_NAMES for part in relative_path.parts)
):
    continue
```

**跳过逻辑从字符串匹配升级成了路径组件匹配**：`EXCLUDED_DIRECTORY_NAMES` 集合包含 `.git`、`.venv`、`env`、`__pycache__`、`data` 等——**项目自身源码作为知识库时，这些目录必须排除**（否则会把 `.git` 历史、venv 里的第三方库全索引进去）。`relative_path.parts` 拆成路径组件逐个判断，比 `in file_path` 字符串匹配更精确。

**编码健壮性**：优先 UTF-8；`UnicodeDecodeError` 时降级 `latin-1` 再试——保证个别编码奇怪的文件不拖垮整个索引。

**输出路径用相对路径 + 正斜杠**：

```python
"path": relative_path.as_posix(),
```

`as_posix()` 把 Windows 反斜杠统一转成正斜杠，跨平台可移植，也保证 `(source, chunk_index)` 融合键稳定。

**② 打 `source_type` + `knowledge_base` 标签 — 隔离基础**

```python
for c in chunks:
    c["metadata"]["source_type"] = "system"
    c["metadata"]["knowledge_base"] = knowledge_base.id
```

每个系统 chunk 打上 `source_type: "system"`，还多了 `knowledge_base: "tinydb" / "project"` 标签。这样在线检索时 `where={"source_type": "system"}` 就只搜系统语料；用户上传的 chunk 是 `"user_upload"`，天然分开。

**③ 多知识库建索引**

```python
async def create_index(knowledge_base_id: str = DEFAULT_KNOWLEDGE_BASE):
    knowledge_base = get_knowledge_base(knowledge_base_id)
    documents = load_code_files(knowledge_base.repo_path)
    ...
    retriever = DenseRetriever(collection_name=knowledge_base.collection_name)
    retriever.delete_collection()
    retriever = DenseRetriever(collection_name=knowledge_base.collection_name)
    retriever.add_chunks(chunks)
    sparse = SparseRetriever.from_chunks(chunks, knowledge_base.collection_name)
```

`create_index` 现在接收 `knowledge_base_id`，按知识库的 `repo_path` 读代码、按 `collection_name` 建索引。**每个知识库的索引互相独立**，重建 tinydb 不会动 project。

**④ 重建全部知识库**

```python
async def rebuild_all_indices():
    results = {}
    for knowledge_base_id in KNOWLEDGE_BASES:
        results[knowledge_base_id] = await create_index(knowledge_base_id)
    return results
```

`__main__` 入口现在调用 `rebuild_all_indices()`——一次脚本把所有知识库全部重建。`finally` 里 `engine.dispose()` 确保脚本退出前关掉数据库连接。

**⑤ 写版本记录**

```python
await save_version_record(strategy=..., chunk_size=..., file_count=..., chunk_count=...)
```

写 `index_versions` 表——这次索引用什么配置建的、多少个文件多少个块，可追溯（配合 evaluation 做交叉分析）。

### 面试答题要点

> **Q：为什么要离线建索引？**
> 答：建索引要加载嵌入模型、对全部代码向量化，耗时以分钟计，不可能每次请求都做。所以一次离线建好（脚本/启动任务），在线查询只做检索。稠密索引存 Chroma，BM25 索引存内存 + Redis 备份。

> **Q：多知识库的索引怎么隔离？**
> 答：每个知识库一个 Chroma collection（`system_code` / `project_code`）+ 一个 BM25 Redis key。`rebuild_all_indices` 逐个重建，互不干扰。新增知识库只需在 `KNOWLEDGE_BASES` 注册。

> **Q：索引项目自身源码时怎么避免误索引垃圾目录？**
> 答：`EXCLUDED_DIRECTORY_NAMES` 集合排除 `.git`、`.venv`、`env`、`data` 等，用路径组件匹配精确判断。否则会把 .git 历史、venv 依赖全塞进索引。

> **Q：重建索引为什么先删后建？**
> 答：保证索引一致性，不会出现新旧 chunk 混合。delete_collection 清空后重新 add。

> **Q：为什么跳过硬编码绝对路径、用 relpath？**
> 答：索引里存相对路径（如 `tinydb/storages.py`）可移植，换机器、换目录都能定位，也保证 `(source, chunk_index)` 融合键稳定。

---

## 4.9 user_upload.py — 用户上传隔离检索

### 完整代码

```python
"""用户文件上传索引：按 owner_id 隔离 + 检索"""

from app.rag.chunker import CodeChunker
from app.rag.dense_retriever import DenseRetriever, USER_CORPUS, USER_UPLOAD_COLLECTION
from app.logger import log


class UserUploadIndex:
    """管理用户上传文件的索引（按 owner_id 隔离）"""

    def __init__(self):
        # 上传内容与系统语料使用独立 collection，避免系统重建索引时删除用户数据。
        self.retriever = DenseRetriever(collection_name=USER_UPLOAD_COLLECTION)

    def add_file(self, filename: str, content: str, owner_id: int) -> int:
        """索引一个上传的文件，返回生成的 chunk 数

        给每个 chunk 写入 owner_id + source_type 元数据，用于检索时隔离。
        """
        documents = [{"path": f"upload/{filename}", "content": content}]
        chunker = CodeChunker()
        chunks = chunker.chunk(documents)

        for c in chunks:
            c["metadata"]["source_type"] = "user_upload"
            c["metadata"]["owner_id"] = owner_id

        self.retriever.add_chunks(chunks)
        log.info("Indexed upload %s (owner=%d) -> %d chunks", filename, owner_id, len(chunks))
        return len(chunks)

    def search(self, query: str, owner_id: int, k: int = 5) -> list[dict]:
        """只检索指定用户上传的文档

        通过 Chroma metadata filter 在检索端隔离：
        {"source_type": "user_upload", "owner_id": owner_id}
        """
        if not query or not query.strip():
            return []

        where = {**USER_CORPUS, "owner_id": owner_id}
        results = self.retriever.search(query, k=k, where=where)

        # 兜底过滤：防止 Chroma filter 兼容问题导致越权
        return [r for r in results
                if str(r.get("source", "")).startswith("upload/")
                and r.get("owner_id") == owner_id]
```

### 这段代码解决什么问题

让用户上传自己的代码文件，索引后**只能搜到自己的**——这是数据隔离 / 防越权的核心。安全设计是三层（比早期版本多了一层物理隔离）：

```
第 0 层：物理隔离   user_uploads 是独立 Chroma collection，与系统代码完全分开
第 1 层：metadata filter   where={"source_type": "user_upload", "owner_id": 你的id}
第 2 层：应用层兜底过滤    source 必须以 "upload/" 开头 且 owner_id 匹配
```

**关键变化**：早期版本用户上传和系统代码在**同一个 Chroma collection**（只靠 metadata 区分），系统重建索引的 `delete_collection()` 会把用户数据一起删掉。现在 `UserUploadIndex` 用 `DenseRetriever(collection_name=USER_UPLOAD_COLLECTION)` 操作**独立的 `user_uploads` collection**——重建系统索引（`system_code` / `project_code`）永远碰不到用户数据。

### 关键代码逐句拆解

**① `add_file` — 索引上传文件**

```python
documents = [{"path": f"upload/{filename}", "content": content}]
chunker = CodeChunker()
chunks = chunker.chunk(documents)

for c in chunks:
    c["metadata"]["source_type"] = "user_upload"
    c["metadata"]["owner_id"] = owner_id
```

- 路径前缀 `upload/`：**这是后续兜底过滤的标记**——只有用户上传的内容才有这个前缀，系统语料没有。
- 每个 chunk 打两重标签：`source_type="user_upload"` + `owner_id=用户id`。
- 写入 `user_uploads` 独立 collection（`self.retriever` 构造时指定）。

**② `search` — 双重隔离检索**

```python
where = {**USER_CORPUS, "owner_id": owner_id}
results = self.retriever.search(query, k=k, where=where)

return [r for r in results
        if str(r.get("source", "")).startswith("upload/")
        and r.get("owner_id") == owner_id]
```

第一层：`where` 过滤——Chroma 只在满足 `source_type="user_upload"` 且 `owner_id=当前用户` 的 chunk 里检索。

第二层：**应用层兜底**——即使 Chroma 的 filter 行为有 bug（比如版本兼容问题导致 filter 失效），返回结果再过滤一遍：`source` 必须以 `upload/` 开头、`owner_id` 必须等于当前用户。**两重验证，即使某一层失效也越不了权。**

这是"纵深防御"（defense in depth）思想的体现，也是面试官最想听到的安全设计。

### 面试答题要点

> **Q：用户上传的文件怎么做到互不可见？**
> 答：三层。**物理层**：上传内容存独立的 `user_uploads` collection；**metadata 层**：检索时 Chroma filter 按 `owner_id=当前用户` 过滤；**应用层**：返回前再校验 source 前缀 + owner_id。三层防护。

> **Q：为什么要有应用层兜底？**
> 答：因为依赖第三方库（Chroma）的 filter 行为有不确定性（版本兼容、边界情况）。安全隔离不能只信一层——即使 filter 失效，第二层校验仍能挡住越权访问。这是纵深防御。

> **Q：系统重建索引会不会删掉用户上传？**
> 答：不会。早期版本两者在同一个 collection，`delete_collection()` 会误删用户数据；现在 `user_uploads` 是独立 collection，系统重建只删 `system_code` / `project_code`。这是本轮修复的关键改进。

---

## 4.10 test_set.py — 评测测试集

### 完整代码

```python
"""测试集：代码检索问题与期望结果"""

TEST_SET_VERSION = "tinydb-retrieval-v1"


TEST_SET = [
    {
        "query": "TinyDB 如何初始化和管理默认表？",
        "expected_sources": ["tinydb/database.py"],
    },
    {
        "query": "TinyDB 支持哪些存储后端，如何配置？",
        "expected_sources": ["tinydb/storages.py"],
    },
    {
        "query": "Query 模块如何实现字段查找和比较？",
        "expected_sources": ["tinydb/queries.py"],
    },
    {
        "query": "TinyDB 中如何创建、缓存和访问表？",
        "expected_sources": ["tinydb/table.py"],
    },
    {
        "query": "TinyDB 的中间件机制是如何处理操作链的？",
        "expected_sources": ["tinydb/middlewares.py"],
    },
    {
        "query": "TinyDB 在存储层如何保证原子写入？",
        "expected_sources": ["tinydb/storages.py"],
    },
    {
        "query": "有哪些查询操作可以检查元素是否在列表中？",
        "expected_sources": ["tinydb/queries.py"],
    },
    {
        "query": "Table.insert 方法如何工作，返回什么？",
        "expected_sources": ["tinydb/table.py"],
    },
    {
        "query": "TinyDB 如何处理 JSON 序列化来存储文档？",
        "expected_sources": ["tinydb/storages.py", "tinydb/database.py"],
    },
    {
        "query": "Storage 基类的作用是什么，如何继承它实现自定义存储？",
        "expected_sources": ["tinydb/storages.py"],
    },
    {
        "query": "TinyDB 如何实现逻辑 OR 和 AND 组合查询？",
        "expected_sources": ["tinydb/queries.py"],
    },
    {
        "query": "Table 类如何处理文档 ID 和 ID 计数器？",
        "expected_sources": ["tinydb/table.py"],
    },
    {
        "query": "TinyDB 如何保证线程安全或处理并发访问？",
        "expected_sources": ["tinydb/database.py", "tinydb/storages.py"],
    },
    {
        "query": "operations 模块如何处理更新数组字段？",
        "expected_sources": ["tinydb/operations.py"],
    },
    {
        "query": "TinyDB 如何清空表和删除所有文档？",
        "expected_sources": ["tinydb/table.py"],
    },
    {
        "query": "存储层在读写数据时使用了什么缓存策略？",
        "expected_sources": ["tinydb/storages.py"],
    },
    {
        "query": "TinyDB 的 search 方法是如何查找匹配文档的？",
        "expected_sources": ["tinydb/table.py"],
    },
    {
        "query": "TinyDB 的 JSONStorage 如何读取和写入文件？",
        "expected_sources": ["tinydb/storages.py"],
    },
    {
        "query": "使用 update 方法更新文档时具体发生了什么？",
        "expected_sources": ["tinydb/table.py"],
    },
    {
        "query": "Query 类如何实现基于哈希的查找和缓存？",
        "expected_sources": ["tinydb/queries.py"],
    },
]
```

### 这段代码解决什么问题

**评估检索效果的"标准答案"**。20 条中文问题，每条标注了"这个问题应该命中哪些源文件"。这是所有评估指标（Hit Rate / MRR / NDCG）的基础——**没有测试集，就没有评估；没有评估，就没有"我的检索到底好不好"的答案**。

设计上几个要点：
- **问题覆盖 TinyDB 核心模块**：database、storages、queries、table、middlewares、operations——每个模块都有对应问题，保证评估的全面性。
- **`expected_sources` 是"期望命中的源文件列表"**，有些问题有多个期望源（如"JSON 序列化"同时期望 storages 和 database）——因为答案可能跨文件。
- 问题是**中文自然语言**，不是代码关键词——这正是考验 RAG 的地方：语义检索能否把中文问题匹配到英文代码。

### 面试答题要点

> **Q：测试集怎么设计的？**
> 答：覆盖知识库（TinyDB）的每个核心模块，每个模块配 1-3 个问题；期望源文件标注到具体文件。问题用中文自然语言描述，考察检索的语义理解能力，而不是简单关键词匹配。

> **Q：指标是什么？**
> 答：Hit Rate（前 k 个结果里有没有期望文件）、MRR（第一个相关结果的倒数排名）、NDCG（考虑排序质量的折损累计增益）。详见 evaluation.py。

---

## 4.11 evaluation.py — 评估引擎与消融实验

### 完整代码

```python
"""评估引擎：测试集评估 + 指标计算 + 消融实验"""

import time
from app.rag.test_set import TEST_SET, TEST_SET_VERSION
from app.rag.dense_retriever import DenseRetriever, SYSTEM_CORPUS
from app.rag.sparse_retriever import SparseRetriever
from app.rag.fusion import rrf
from app.rag.reranker import Reranker
from app.rag.query_rewriter import rewrite
from app.logger import log


def _normalize(source: str) -> str:
    """统一路径分隔符：Windows 反斜杠 → 正斜杠"""
    return source.replace("\\", "/")


def hit_rate(results: list[dict], expected_sources: list[str], k: int = 5) -> float:
    """Hit Rate@k：前k个结果中是否包含至少一个期望的源文件"""
    top_k = results[:k]
    actual_sources = {_normalize(r["source"]) for r in top_k}
    for expected in expected_sources:
        if any(_normalize(expected) in src for src in actual_sources):
            return 1.0
    return 0.0


def mrr(results: list[dict], expected_sources: list[str], k: int = 5) -> float:
    """MRR@k：第一个相关结果的倒数排名"""
    for rank, r in enumerate(results[:k]):
        src = _normalize(r["source"])
        for expected in expected_sources:
            if _normalize(expected) in src:
                return 1.0 / (rank + 1)
    return 0.0


def ndcg(results: list[dict], expected_sources: list[str], k: int = 5) -> float:
    """NDCG@k：归一化折损累积增益（二值相关性）"""
    dcg = 0.0
    matched = set()
    for i, r in enumerate(results[:k]):
        src = _normalize(r["source"])
        rel = 0.0
        for e in expected_sources:
            e_norm = _normalize(e)
            if e_norm in src and e_norm not in matched:
                rel = 1.0
                matched.add(e_norm)
                break
        dcg += rel / (i + 1)

    idcg = 0.0
    for i in range(min(k, len(expected_sources))):
        idcg += 1.0 / (i + 1)

    return dcg / idcg if idcg > 0 else 0.0


async def evaluate_config(
    dense: bool = True,
    sparse: bool = True,
    hyde: bool = False,
    reranker: bool = False,
    top_k: int = 5,
) -> dict:
    """
    运行一轮评估，返回聚合指标
    参数控制消融实验：关掉某个组件就看指标怎么掉
    """
    dense_retriever = DenseRetriever() if dense else None
    sparse_retriever = SparseRetriever.from_redis() if sparse else None
    if sparse_retriever and sparse_retriever.count() == 0:
        raise RuntimeError(
            "BM25 index is unavailable. Rebuild the system index before running evaluation."
        )
    reranker_instance = Reranker() if reranker else None

    total_hit_rate = 0.0
    total_mrr = 0.0
    total_ndcg = 0.0
    total_latency = 0.0
    n = len(TEST_SET)

    for item in TEST_SET:
        query = item["query"]
        expected = item["expected_sources"]
        start = time.time()

        # 第一步：查询改写（HyDE）
        if hyde:
            query = await rewrite(query, strategy="hyde")

        # 第二步：检索（直接同步调用，不走线程池）
        dense_results = []
        sparse_results = []

        if dense_retriever:
            dense_results = dense_retriever.search(
                query, top_k * 2, where=SYSTEM_CORPUS
            )

        if sparse_retriever:
            sparse_results = sparse_retriever.search(query, top_k * 2)

        # 第三步：融合
        if dense_results and sparse_results:
            fused = rrf([dense_results, sparse_results], top_n=top_k * 2)
        elif dense_results:
            fused = dense_results[:top_k * 2]
        elif sparse_results:
            fused = sparse_results[:top_k * 2]
        else:
            fused = []

        # 第四步：重排序
        if reranker_instance and fused:
            fused = reranker_instance.rerank(query, fused, top_n=top_k)
        else:
            fused = fused[:top_k]

        latency = time.time() - start
        total_latency += latency

        # 单条日志：谁 + 搜到什么 + 得分
        log.info(
            "[%s] Q: %s... → hits=%d | HR=%.2f MRR=%.2f NDCG=%.2f | %.0fms",
            "HYDE" if hyde else "DIRECT",
            query[:40],
            len(fused),
            hit_rate(fused, expected, k=top_k),
            mrr(fused, expected, k=top_k),
            ndcg(fused, expected, k=top_k),
            latency * 1000,
        )

        # 计算指标
        total_hit_rate += hit_rate(fused, expected, k=top_k)
        total_mrr += mrr(fused, expected, k=top_k)
        total_ndcg += ndcg(fused, expected, k=top_k)

    return {
        "hit_rate": round(total_hit_rate / n, 4),
        "mrr": round(total_mrr / n, 4),
        "ndcg": round(total_ndcg / n, 4),
        "avg_latency_ms": round(total_latency / n * 1000, 2),
        "test_set_size": n,
        "config": {
            "dataset_version": TEST_SET_VERSION,
            "dense": dense,
            "sparse": sparse,
            "hyde": hyde,
            "reranker": reranker,
        },
    }


async def run_ablation(experiment_name: str = "ablation_v1"):
    """
    跑完全部消融实验组合，写入 evaluation_runs 表
    """
    configs = [
        {"dense": True,  "sparse": False, "hyde": False, "reranker": False},
        {"dense": False, "sparse": True,  "hyde": False, "reranker": False},
        {"dense": True,  "sparse": True,  "hyde": False, "reranker": False},
        {"dense": True,  "sparse": True,  "hyde": True,  "reranker": False},
        {"dense": True,  "sparse": True,  "hyde": True,  "reranker": True},
    ]

    names = [
        "dense_only",
        "sparse_only",
        "hybrid_baseline",
        "hybrid_with_hyde",
        "hybrid_with_hyde_and_reranker",
    ]

    results = []
    for cfg, name in zip(configs, names):
        log.info("Running: %s", name)
        print(f"\n--- [{name}] ---")
        result = await evaluate_config(**cfg)
        results.append((name, result))

    # 打印对比表
    print(f"\n{'='*80}")
    print(f"Experiment: {experiment_name}")
    print(f"{'='*80}")
    print(f"{'Config':<30} {'Hit Rate':<10} {'MRR':<10} {'NDCG':<10} {'Latency(ms)':<12}")
    print(f"{'-'*72}")
    for name, r in results:
        print(f"{name:<30} {r['hit_rate']:<10.4f} {r['mrr']:<10.4f} {r['ndcg']:<10.4f} {r['avg_latency_ms']:<12.2f}")
    print(f"{'='*80}")

    # 写入数据库
    from app.database import async_session_factory
    from app.models.evaluation_run import EvaluationRun

    async with async_session_factory() as session:
        for name, r in results:
            session.add(EvaluationRun(
                run_name=f"{experiment_name}_{name}",
                config=r["config"],
                test_set_size=r["test_set_size"],
                hit_rate=r["hit_rate"],
                mrr=r["mrr"],
                ndcg=r["ndcg"],
                avg_latency_ms=r["avg_latency_ms"],
            ))
        await session.commit()

    log.info("Ablation results saved to database")
    return results
```

### 这段代码解决什么问题

**用数据回答"我的检索到底好不好、哪个组件有用"。** 它实现了三个评估指标，并跑 5 组"消融实验"——每次关掉一个组件（比如不用 HyDE、不用 reranker），对比指标变化。

### 关键代码逐句拆解

**① `_normalize` — 跨平台路径**

```python
def _normalize(source: str) -> str:
    return source.replace("\\", "/")
```

Windows 路径分隔符是 `\`，Linux 是 `/`。测试集里写的期望源是 `tinydb/database.py`（正斜杠），而 Windows 上索引出来的 source 可能是 `tinydb\database.py`。归一化后两边才能比对。**这是 CI（Linux）和本地（Windows）结果不一致的典型坑**。

**② `hit_rate` — 命中率**

```python
def hit_rate(results, expected_sources, k=5):
    top_k = results[:k]
    actual_sources = {_normalize(r["source"]) for r in top_k}
    for expected in expected_sources:
        if any(_normalize(expected) in src for src in actual_sources):
            return 1.0
    return 0.0
```

**前 k 个结果里只要出现至少一个期望源文件，就算命中**，返回 1.0；否则 0.0。注意用 `in`（子串匹配）而不是 `==`：因为期望是文件路径，实际 source 可能带路径前缀。

**③ `mrr` — 平均倒数排名**

```python
def mrr(results, expected_sources, k=5):
    for rank, r in enumerate(results[:k]):
        src = _normalize(r["source"])
        for expected in expected_sources:
            if _normalize(expected) in src:
                return 1.0 / (rank + 1)
    return 0.0
```

**第一个相关结果排第几？** 排第 1 → 1.0，排第 2 → 0.5，排第 3 → 0.33……没找到 → 0。MRR 比 Hit Rate 更严格——Hit Rate 只关心"有没有"，MRR 关心"排多靠前"。

**④ `ndcg` — 归一化折损累计增益**

```python
dcg += rel / (i + 1)    # 位置 i（0 基）折损因子 1/(i+1)
...
idcg = sum(1/(i+1) for i in range(min(k, len(expected_sources))))
return dcg / idcg if idcg > 0 else 0.0
```

NDCG 是"排序质量"指标：相关文档排在前面 → 得分高；排得越靠后，贡献被折损得越多。**用 IDCG（理想排序下的最大得分）归一化**，让不同长度的查询可比。

细节：`matched` 集合保证**同一个源文件出现多个 chunk 只算一次相关性**——防止同一个文件刷分。

**⑤ `evaluate_config` — 单组评估**

```python
async def evaluate_config(dense=True, sparse=True, hyde=False, reranker=False, top_k=5):
    ...
    for item in TEST_SET:
        if hyde:
            query = await rewrite(query, strategy="hyde")
        ...
        dense_results = dense_retriever.search(query, top_k * 2)
        sparse_results = sparse_retriever.search(query, top_k * 2)
        ...
        fused = rrf([dense_results, sparse_results], top_n=top_k * 2)
        ...
        if reranker_instance and fused:
            fused = reranker_instance.rerank(query, fused, top_n=top_k)
```

**参数控制组件开关**——这就是"消融"：把每个组件当开关，关掉看指标怎么变。链路复现了在线检索：改写 → 双路召回 → RRF → 重排。

注意：召回 `top_k * 2`（留余量），融合后 `top_k * 2`，重排/截断到 `top_k`。

**⑥ `run_ablation` — 5 组消融**

```python
configs = [
    {"dense": True,  "sparse": False, ...},  # dense_only
    {"dense": False, "sparse": True,  ...},  # sparse_only
    {"dense": True,  "sparse": True,  ...},  # hybrid_baseline
    {... "hyde": True,  ...},               # hybrid + HyDE
    {... "hyde": True,  "reranker": True},  # hybrid + HyDE + rerank
]
```

跑完打印对比表，并写入 `evaluation_runs` 表。**这就是 README 里那张消融表的来源**（下面是最新一轮修复 BM25 空索引后重跑的数据）：

| 配置 | Hit Rate | MRR | NDCG | 延迟(ms) |
|------|----------|-----|------|----------|
| dense_only | 0.95 | 0.60 | 0.60 | 12.87 |
| sparse_only | 0.70 | 0.45 | 0.44 | 0.05 |
| hybrid_baseline | 1.00 | 0.59 | 0.58 | 0.89 |
| hybrid + HyDE | 1.00 | 0.59 | 0.58 | 3607.83 |
| hybrid + HyDE + rerank | 0.85 | 0.49 | 0.48 | 3720.40 |

> **注**：这组数据是在修复"BM25 空索引"bug 后重跑的。修复前 `SparseRetriever()` 直接构造导致稀疏路静默返回空，sparse_only 实验实际是空跑、hybrid 实验退化成纯 dense，旧数据（sparse_only 0.95 / hybrid 0.95）不可信。修复后 `from_redis()` 加载真实索引，才得到上面可信的数据。

### 面试答题要点

> **Q：Hit Rate、MRR、NDCG 分别衡量什么？**
> 答：Hit Rate 衡量"有没有找到"（前 k 个里是否含期望结果）；MRR 衡量"找得多靠前"（第一个相关结果的倒数排名）；NDCG 衡量"整体排序质量"（相关结果越靠前分越高，且用理想排序归一化）。

> **Q：消融实验的结果说明了什么？**
> 答：三件事。① **混合检索（dense + BM25 + RRF）Hit Rate 达 1.00**，优于单路 dense（0.95）和单路 sparse（0.70）——证明双路召回互补有效，这是修复 BM25 空索引后最关键的发现；但融合在少数 case 把正确结果从首位挤后，MRR/NDCG 较 dense_only 微降（0.60 → 0.59），属于命中率与排序精度的权衡。② **HyDE 无增量**（命中率不变）但延迟从 0.89ms 飙到 3607ms，默认关闭。③ **reranker 降分**（1.00 → 0.85），模型在网页搜索领域训练、对代码不敏感。结论：**组件必须按领域验证，不能无脑叠加**。

> **Q：这个结论对你有何启发？**
> 答：面试可以主动讲——"我做过消融实验，还发现并修复了一个真实 bug（BM25 空索引导致消融数据不可信），修复后重跑，数据发生了两个关键变化：sparse_only 从 0.95 变成真实的 0.70，hybrid 从 0.95 升到 1.00——这反过来证明了双路融合确实有增量。RAG 优化要根据数据和场景验证。"这比"我用了所有最先进的技术"更有说服力。

> **Q：为什么路径要归一化？**
> 答：Windows 用反斜杠、Linux 用正斜杠，测试集里期望源是正斜杠。不归一化，同一结果在本地（Windows）和 CI（Linux）会判出不同命中。

---

## 4.12 scripts/eval_ragas.py — 端到端 RAGAS 评估脚本

### 完整代码

```python
"""Optional RAGAS evaluation for the TinyDB retrieval-and-answer pipeline.

Install with ``python -m pip install -r requirements-eval.txt``. The script
uses the configured LLM as the judge unless RAGAS_JUDGE_* variables override
it. It makes paid judge calls and should be run deliberately, not in CI.
"""

import argparse
import json
import os
from pathlib import Path

from app.agent.eval_tasks import EVAL_TASKS
from app.agent.llm import call_llm
from app.config import settings
from app.rag.knowledge_bases import (
    DEFAULT_KNOWLEDGE_BASE,
    KNOWLEDGE_BASES,
    get_knowledge_base,
)


PROJECT_EVAL_SET_PATHS = (
    Path(__file__).resolve().parents[1] / "data" / "eval" / "project_eval_set.json",
    Path(__file__).resolve().parents[1] / "data" / "eval" / "project_eval_set_extra.json",
)


def load_eval_tasks(knowledge_base_id: str) -> list[dict]:
    """Load the reviewed test set for a supported public knowledge base."""
    if knowledge_base_id == "tinydb":
        return EVAL_TASKS
    if knowledge_base_id == "project":
        tasks = []
        for path in PROJECT_EVAL_SET_PATHS:
            with path.open(encoding="utf-8") as file:
                tasks.extend(json.load(file))
        return tasks
    raise ValueError(f"No evaluation set for knowledge base '{knowledge_base_id}'")


def retrieve_contexts(
    question: str,
    knowledge_base_id: str = DEFAULT_KNOWLEDGE_BASE,
    top_k: int = 5,
) -> list[str]:
    """Use the production Hybrid RAG retrieval path for each evaluation item."""
    from app.rag.dense_retriever import DenseRetriever, SYSTEM_CORPUS
    from app.rag.fusion import rrf
    from app.rag.sparse_retriever import SparseRetriever

    knowledge_base = get_knowledge_base(knowledge_base_id)
    dense = DenseRetriever(collection_name=knowledge_base.collection_name)
    sparse = SparseRetriever.from_redis(knowledge_base.collection_name)
    if sparse.count() == 0:
        raise RuntimeError(
            f"BM25 index for '{knowledge_base.id}' is unavailable. "
            "Start Redis and rebuild that knowledge base first."
        )

    dense_results = dense.search(question, k=top_k * 2, where=SYSTEM_CORPUS)
    sparse_results = sparse.search(question, k=top_k * 2)
    fused = rrf([dense_results, sparse_results], top_n=top_k)
    return [result["text"] for result in fused]


def answer_with_context(
    question: str,
    contexts: list[str],
    knowledge_base_id: str = DEFAULT_KNOWLEDGE_BASE,
) -> str:
    evidence = "\n\n---\n\n".join(contexts)
    prompt = (
        f"Question:\n{question}\n\n"
        f"Retrieved code context:\n{evidence}\n\n"
        "Answer only from the retrieved context. If it is insufficient, say so."
    )
    return call_llm(
        prompt,
        system_prompt=(
            f"You are a careful {get_knowledge_base(knowledge_base_id).label} "
            "code assistant. Answer in Chinese."
        ),
    )


def build_samples(knowledge_base_id: str = DEFAULT_KNOWLEDGE_BASE) -> list[dict]:
    """Build the RAGAS question, context, answer, and reference contract."""
    samples = []
    for task in load_eval_tasks(knowledge_base_id):
        contexts = retrieve_contexts(task["question"], knowledge_base_id)
        answer = answer_with_context(task["question"], contexts, knowledge_base_id)
        samples.append({
            "question": task["question"],
            "contexts": contexts,
            "answer": answer,
            "ground_truth": task["reference"],
        })
    return samples


def _judge_base_url(endpoint: str) -> str:
    suffix = "/chat/completions"
    if not endpoint.endswith(suffix):
        raise RuntimeError(
            "RAGAS requires an OpenAI-compatible chat-completions endpoint."
        )
    return endpoint[:-len(suffix)]


def run(knowledge_base_id: str = DEFAULT_KNOWLEDGE_BASE) -> None:
    try:
        from datasets import Dataset
        from langchain_community.embeddings import HuggingFaceEmbeddings
        from langchain_openai import ChatOpenAI
        from ragas import evaluate
        from ragas.metrics import answer_correctness, context_precision
    except ImportError as exc:
        import traceback
        traceback.print_exc()
        raise SystemExit(
            "Install optional evaluation dependencies first: "
            "python -m pip install -r requirements-eval.txt"
        ) from exc

    judge_endpoint = os.getenv("RAGAS_JUDGE_ENDPOINT", settings.LLM_API_ENDPOINT)
    judge_model = os.getenv("RAGAS_JUDGE_MODEL", settings.LLM_MODEL)
    judge_key = os.getenv("RAGAS_JUDGE_API_KEY", settings.LLM_API_KEY)
    if not judge_key:
        raise SystemExit("RAGAS_JUDGE_API_KEY or LLM_API_KEY must be configured.")

    judge = ChatOpenAI(
        model=judge_model,
        openai_api_key=judge_key,
        openai_api_base=_judge_base_url(judge_endpoint),
        temperature=0,
    )
    local_embeddings = HuggingFaceEmbeddings(
        model_name=settings.EMBEDDING_MODEL,
        model_kwargs={"device": settings.EMBEDDING_DEVICE},
    )
    dataset = Dataset.from_list(build_samples(knowledge_base_id))
    result = evaluate(
        dataset,
        metrics=[context_precision, answer_correctness],
        llm=judge,
        embeddings=local_embeddings,
    )
    print(result)
    print(
        f"RAGAS is an LLM-judge result on the '{knowledge_base_id}' reviewed set; "
        "record the model, prompt, index version, and run date with every result."
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--knowledge-base",
        choices=sorted(KNOWLEDGE_BASES),
        default=DEFAULT_KNOWLEDGE_BASE,
    )
    arguments = parser.parse_args()
    run(arguments.knowledge_base)
```

### 这段代码解决什么问题

这是**可选的端到端 RAGAS 评估脚本**——用 LLM-as-Judge 评估"检索 + 生成"的最终质量，和 `evaluation.py`（检索指标 Hit Rate/MRR/NDCG）互补。

**和 `evaluation.py` 的区别**：`evaluation.py` 只测检索（看检出的文件对不对）；`eval_ragas.py` 测完整链路——检索上下文 → LLM 基于上下文生成回答 → Judge LLM 给 `context_precision`（检索质量）和 `answer_correctness`（回答质量）打分。

**使用**：
```bash
cd backend
pip install -r requirements-eval.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
python -m scripts.eval_ragas --knowledge-base tinydb    # 或 project
```

### 关键代码逐句拆解

**① 评测集加载 `load_eval_tasks`**

```python
def load_eval_tasks(knowledge_base_id: str) -> list[dict]:
    if knowledge_base_id == "tinydb":
        return EVAL_TASKS                     # eval_tasks.py 的 8 条
    if knowledge_base_id == "project":
        tasks = []
        for path in PROJECT_EVAL_SET_PATHS:
            tasks.extend(json.load(path.open(encoding="utf-8")))
        return tasks                          # data/eval/ 下两个 JSON，34 条
    raise ValueError(...)
```

**两个知识库用不同的评测集**：tinydb 用 `eval_tasks.py` 的人工题；project 用 `data/eval/` 下的两个 JSON（含 question / reference / evidence_sources / category / difficulty）。

**② 检索上下文 `retrieve_contexts`**

```python
dense = DenseRetriever(collection_name=knowledge_base.collection_name)
sparse = SparseRetriever.from_redis(knowledge_base.collection_name)
if sparse.count() == 0:
    raise RuntimeError("BM25 index ... unavailable. ...")
dense_results = dense.search(question, k=top_k * 2, where=SYSTEM_CORPUS)
sparse_results = sparse.search(question, k=top_k * 2)
fused = rrf([dense_results, sparse_results], top_n=top_k)
return [result["text"] for result in fused]
```

**复用生产检索链路**（不是单独的测试实现）：Dense + BM25 + RRF，和线上 `/api/search` 用同一套。**如果 BM25 索引没建，直接抛错**（fail fast，不产出无效分数）。

**③ 生成回答 `answer_with_context`**

```python
prompt = f"Question:\n{question}\n\nRetrieved code context:\n{evidence}\n\nAnswer only from the retrieved context..."
return call_llm(prompt, system_prompt=...)
```

让业务 LLM 基于检索到的代码片段生成回答，要求"只依据检索上下文，不足就明说"。

**④ RAGAS 打分 `run`**

```python
judge = ChatOpenAI(model=judge_model, openai_api_key=judge_key,
                   openai_api_base=_judge_base_url(judge_endpoint), temperature=0)
local_embeddings = HuggingFaceEmbeddings(model_name=settings.EMBEDDING_MODEL, ...)
result = evaluate(dataset, metrics=[context_precision, answer_correctness],
                  llm=judge, embeddings=local_embeddings)
```

- **Judge LLM**：默认用业务 LLM（DeepSeek），可用 `RAGAS_JUDGE_*` 覆盖。`_judge_base_url` 要求端点以 `/chat/completions` 结尾。
- **`context_precision`**：检索上下文对回答的有用程度（注意：ragas 0.1.22 里叫 `context_precision`，不是 `context_relevancy`——后者在旧版不存在）。
- **`answer_correctness`**：回答与 `ground_truth`（参考答案）的一致性。
- **`temperature=0`**：Judge 打分要确定，不能有随机性。

**⑤ 诚实提示**

脚本结尾打印：
```
RAGAS is an LLM-judge result on the 'tinydb' reviewed set; record the model, prompt, index version, and run date with every result.
```

提醒：**记录模型、提示词、索引版本、运行日期**，否则分数不可引用。这是评估可复现性的自我约束。

### 面试答题要点

> **Q：RAGAS 评估和 evaluation.py 的消融实验有什么区别？**
> 答：消融实验（evaluation.py）测检索质量（Hit Rate/MRR/NDCG，看检出的文件对不对）；RAGAS 测端到端（检索 + 生成，Judge LLM 给 context_precision 和 answer_correctness）。一个是中间环节，一个是最终效果。

> **Q：Judge LLM 用什么？**
> 答：默认复用业务 LLM（DeepSeek），可用 `RAGAS_JUDGE_ENDPOINT/MODEL/API_KEY` 覆盖。Judge 打分 `temperature=0` 保证确定性。注意 ragas 0.1.22 的指标主要针对 OpenAI 生态调优，用 DeepSeek 当 judge 分数可能系统性偏低。

> **Q：评测集哪来的？**
> 答：tinydb 用 `eval_tasks.py` 的 8 条人工题；project 用 `data/eval/` 下两个 JSON（34 条，每条含 question / reference / evidence_sources）。这些 JSON 在项目索引排除目录里，避免参考答案泄漏进知识库。

### 第 4 层小结

RAG 管线的 12 个文件 + 1 个评估脚本，按职能分四组：

- **多知识库**：knowledge_bases（定义 tinydb / project 的元信息）。
- **在线链路**：chunker（分块）→ dense（语义）→ sparse（关键词）→ fusion（RRF 融合）→ rewriter（HyDE 改写）→ reranker（精排）。每个组件都是可开关的。
- **离线编排**：code_indexer（按知识库建索引 + 打标签 + 防并发重建）、user_upload（独立 collection + owner 隔离）。
- **评估**：test_set（评测题集）、evaluation（检索指标 + 消融）、scripts/eval_ragas.py（端到端 RAGAS）。

**贯穿全层的思想**：每个组件都有降级路径（模型挂了跳过、缓存挂了降级、改写失败返回原查询）、都有缓存（Redis）、都有日志（可观测）、都有数据支撑（消融实验 + RAGAS）。这就是"工程化 RAG"和"demo RAG"的区别。

---

# 第 5 层 Agent：让模型自己决策

第 4 层的 RAG 是被动的——"你搜我就返回"。第 5 层的 Agent 是**主动的**：让 LLM 自己决定要不要搜、搜什么、搜完怎么答。

项目**没有用 LangGraph**，而是**自己实现了 tool-calling Agent**（从早期手写 ReAct 演进而来），5 个文件：

```
llm.py        LLM 调用封装（文本 + tool-calling，重试 + 退避）
tool_base.py  工具抽象基类（Pydantic args_model + function_schema）
prompt.py     系统提示词（按知识库动态生成）
tools.py      三个工具：search / explain / testgen（绑定知识库）
harness.py    Tool-Calling 循环引擎（校验参数、执行工具、防重复、记轨迹）
```

Agent 的调用关系：`harness` 用 `prompt.build_system_prompt` 构造提示词 → 调 `llm.call_llm_with_tools` 拿结构化回复（含 `tool_calls`）→ 逐个校验参数并执行 `tools` 里的工具 → 工具内部调用 RAG 检索（第 4 层）→ 把 tool 消息注入 → 循环直到 LLM 给出最终答案。

**演进路线**：这个项目最初是手写 ReAct（LLM 输出 Action JSON + 括号深度解析），后来演进到原生 tool-calling（OpenAI 兼容 `tools` 参数 + Pydantic 参数校验）。**先理解原理，再用工业标准方案**——这是面试时最有说服力的叙述。

---

## 5.1 llm.py — LLM 调用封装

### 完整代码

```python
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
```

### 这段代码解决什么问题

统一所有 LLM 调用，解决三个问题：

1. **多服务商兼容**：DeepSeek（OpenAI 兼容格式）和 Ollama（本地格式）响应结构不同，`_parse_response` 统一解析。
2. **稳定性**：LLM 服务不稳定，超时/5xx 自动重试，指数退避。
3. **三种调用场景**：`call_llm`（单 prompt + system）给 HyDE 改写、工具内部用；`call_llm_with_messages`（完整消息列表）给多轮对话；**`call_llm_with_tools`（携带工具 schema）给 Agent 的 tool-calling 循环用**。

### 关键代码逐句拆解

**① `_parse_response` — 兼容两种格式**

```python
def _parse_response(response: dict) -> str:
    # Ollama 格式: {"message": {"content": "..."}}
    if "message" in response:
        return response["message"].get("content", "")
    # OpenAI / DeepSeek 格式: {"choices": [{"message": {"content": "..."}}]}
    if response.get("choices"):
        return response["choices"][0].get("message", {}).get("content", "") or ""
```

Ollama 的 `/api/chat` 返回 `{"message": {"content": "..."}}`；DeepSeek/OpenAI 返回 `{"choices": [{"message": {"content": "..."}}]}`。先判断 `message`（Ollama），再判断 `choices`（OpenAI）。**靠配置切换服务商，代码零改动**。

**② `_parse_assistant_message` — 保留 tool_calls（新）**

```python
def _parse_assistant_message(response: dict) -> dict | None:
    message = choices[0].get("message")
    return {
        "role": "assistant",
        "content": message.get("content"),
        "tool_calls": message.get("tool_calls") or [],
    }
```

这是 **tool-calling 的核心**：OpenAI 兼容接口在 assistant 消息里返回 `tool_calls` 数组（含函数名 + 参数 JSON 字符串）。这个解析器**原样保留** `tool_calls`，让 Agent 循环能拿到结构化工具调用，而不需要从文本里抠 JSON。`or []` 保证没有工具调用时是空列表。

**③ `_post_with_retries` — 抽取公共重试逻辑**

```python
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
            response = httpx.post(settings.LLM_API_ENDPOINT, json=body, ...)
            response.raise_for_status()
            return response.json()
        except httpx.TimeoutException:
            ...
        if attempt < max_retries:
            time.sleep(2 ** attempt)
```

原来的三个调用函数各写一份重试逻辑，现在**抽成公共函数** `_post_with_retries`——所有入口共用一套重试 + 指数退避。失败返回 `None`（区别于 `""`），调用方据此判断。**新增两个参数**：

- `timeout_seconds`：单次请求超时，可由调用方按剩余预算动态传入（Agent 循环用 `min(AGENT_LLM_TIMEOUT_SECONDS, remaining)`）。
- `cancel_event`：**取消信号**——客户端断开时置位，重试前先检查，避免"用户都走了还在打重试"。

**④ `call_llm_with_tools` — Agent 专用入口（新）**

```python
def call_llm_with_tools(messages, tools, max_retries=2,
                        timeout_seconds=60, cancel_event=None) -> dict | None:
    response = _post_with_retries({
        "model": settings.LLM_MODEL,
        "messages": messages,
        "tools": tools,            # ← 工具 schema 列表
        "tool_choice": "auto",     # ← 模型自己决定调不调、调哪个
        "stream": False,
        "temperature": 0.3,
        "max_tokens": 1024,
    }, max_retries, timeout_seconds, cancel_event)
    return _parse_assistant_message(response) if response is not None else None
```

**请求体多了 `tools` 和 `tool_choice`**：
- `tools`：每个工具的函数 schema（`function_schema()` 生成，见 tool_base）。
- `tool_choice: "auto"`：允许模型自主决定是否调用工具。
- 返回**结构化 assistant 消息**（含 `tool_calls`），而不是纯文本。

**④.5 `call_llm_with_messages_stream` — 流式输出（新）**

```python
def call_llm_with_messages_stream(
    messages, on_delta: Callable[[str], None],
    timeout_seconds=60, cancel_event=None,
) -> str:
    with httpx.stream("POST", settings.LLM_API_ENDPOINT, json=body, ...) as response:
        for line in response.iter_lines():
            if cancel_event and cancel_event.is_set():
                break                       # 客户端断开 → 中断流式
            if not line or not line.startswith("data:"):
                continue
            data = line.removeprefix("data:").strip()
            if data == "[DONE]":
                break
            delta = json.loads(data)["choices"][0].get("delta", {}).get("content") or ""
            if delta:
                chunks.append(delta)
                on_delta(delta)              # 实时回调：把增量推给前端
    return "".join(chunks)
```

**这是 SSE 流式对话的底层**：
- 用 `httpx.stream` 建立流式连接，逐行解析 `data:` 前缀的 SSE 帧。
- `delta.content` 是每个 token 增量，通过 `on_delta` 回调**实时推给前端**（配合 agent_router 的 SSE 事件流）。
- `[DONE]` 结束帧、`cancel_event` 中断——客户端断开时及时停止。
- 函数返回**拼接后的完整文本**（Agent 需要完整答案落库），同时通过回调实现了流式展示。

**⑤ 四个函数的定位**

| 函数 | 场景 | 返回 |
|------|------|------|
| `call_llm` | HyDE 改写、工具内部 LLM 加工 | `str` |
| `call_llm_with_messages` | 多轮对话 / 降级总结 | `str` |
| `call_llm_with_messages_stream` | 流式输出最终回答 | `str`（同时回调增量） |
| `call_llm_with_tools` | Agent 循环 | `dict \| None`（含 tool_calls） |

### 面试答题要点

> **Q：怎么支持多个 LLM 服务商？**
> 答：通过配置 `LLM_API_ENDPOINT` 切换，代码不改。关键是 `_parse_response` 兼容两种响应格式（Ollama 的 `message`、OpenAI 的 `choices`）。

> **Q：原生 tool-calling 和"让模型输出 JSON"有什么区别？**
> 答：原生 tool-calling 是 OpenAI 兼容接口的 `tools` 参数，模型**结构化返回** `tool_calls`（函数名 + 参数 JSON），不用自己从文本里用正则/括号深度解析。更可靠，参数校验用 Pydantic。代价是强依赖服务商支持 tools 协议（DeepSeek / OpenAI 支持，部分本地模型不一定）。

> **Q：为什么要有重试和退避？**
> 答：LLM 服务不稳定（超时、5xx）。重试 + 指数退避（1s → 2s）提高成功率，同时避免并发重试把服务打爆。退避防止"雪崩式重试"。

> **Q：cancel_event 是干嘛的？**
> 答：客户端断开（SSE 连接消失）时置位。所有 LLM 调用在重试前检查它——用户都走了还打重试是浪费。这是流式场景的可靠性细节。

> **Q：四个 LLM 入口怎么分工？**
> 答：`call_llm`（单轮文本）给改写和工具加工；`call_llm_with_messages`（多轮文本）给对话和降级总结；`call_llm_with_messages_stream`（流式）给 SSE 最终回答；`call_llm_with_tools`（带工具 schema）给 Agent 循环。四者共用 `_post_with_retries` 的重试 + 取消逻辑。

---

## 5.2 tool_base.py — 工具抽象基类

### 完整代码

```python
"""Base class and schemas for allow-listed Agent tools."""

from abc import ABC, abstractmethod

from pydantic import BaseModel


class Tool(ABC):
    name: str = ""
    description: str = ""
    args_model: type[BaseModel] | None = None

    def function_schema(self) -> dict:
        """Return the OpenAI-compatible function schema exposed to the model."""
        if self.args_model is None:
            raise ValueError(f"Tool '{self.name}' must define an args_model")

        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.args_model.model_json_schema(),
            },
        }

    def validate_args(self, args: dict) -> dict:
        """Validate untrusted model arguments before a tool is executed."""
        if self.args_model is None:
            raise ValueError(f"Tool '{self.name}' must define an args_model")
        return self.args_model.model_validate(args).model_dump()

    @abstractmethod
    def execute(self, **kwargs) -> str:
        """Execute the tool and return a text observation."""
        pass
```

### 这段代码解决什么问题

定义"工具长什么样"。所有 Agent 工具（search / explain / testgen）都继承 `Tool`，必须实现 `execute`。

**相比早期版本（name/description/parameters 都是普通属性），现在最大的变化是引入 `args_model`**——用 Pydantic 模型声明工具参数，自动生成给 LLM 的 schema，并在执行前校验参数。

### 关键代码逐句拆解

**① `args_model` — 参数即 Pydantic 模型**

```python
args_model: type[BaseModel] | None = None
```

每个工具声明一个 Pydantic 模型描述它的参数。比如 `SearchArgs(BaseModel): query: str = Field(min_length=1, max_length=300)`。这比手写 `parameters: dict` 强得多：

- **自动生成 schema**：`model_json_schema()` 输出 JSON Schema，直接给 LLM 当工具签名。
- **自动校验**：`model_validate(args)` 校验类型、长度、必填，非法的参数根本不会执行。

**② `function_schema` — 给 LLM 看的"工具说明书"**

```python
def function_schema(self) -> dict:
    return {
        "type": "function",
        "function": {
            "name": self.name,
            "description": self.description,
            "parameters": self.args_model.model_json_schema(),
        },
    }
```

这是 **OpenAI 兼容的工具 schema**，请求体里的 `tools` 数组就是由它拼成的。`model_json_schema()` 把 Pydantic 模型转成标准 JSON Schema——**LLM 靠它知道"这个工具有哪些参数、参数什么类型"**。

**③ `validate_args` — 执行前校验不可信参数**

```python
def validate_args(self, args: dict) -> dict:
    return self.args_model.model_validate(args).model_dump()
```

模型（LLM）返回的参数是"不可信输入"——可能是错的类型、超长、缺字段。**执行前必须过 Pydantic 校验**：`model_validate` 校验，`.model_dump()` 转回普通 dict。校验失败抛 `ValidationError`，Agent 循环会捕获并把错误作为 observation 告诉 LLM。

**④ `ABC` + `@abstractmethod`**

实例化 `Tool()` 会报错，强制子类实现 `execute`。同时所有工具必须定义 `name`、`description`、`args_model`。

### 面试答题要点

> **Q：为什么工具参数用 Pydantic 模型而不是普通 dict？**
> 答：Pydantic 给两件事兜底：一是 `model_json_schema()` 自动生成给 LLM 的 JSON Schema（不用手写）；二是 `model_validate()` 在执行前校验模型传入的参数——非法参数直接拒绝，不会带着脏数据执行工具。这是"不可信输入必须校验"的安全实践。

> **Q：function_schema 是什么？**
> 答：OpenAI 兼容的函数 schema（type: function + name + description + parameters）。Agent 循环把它放进请求体的 `tools` 数组，LLM 才能"知道"有哪些工具、怎么调。

> **Q：为什么用抽象基类？**
> 答：强制统一接口（每个工具都必须实现 execute），同时保证所有工具都带 name/description/args_model，让工具注册制（新增工具自动注入 schema）成为可能。

---

## 5.3 prompt.py — 系统提示词

### 完整代码

```python
"""System prompts for the selected code knowledge base."""

FUNCTION_CALLING_SYSTEM_PROMPT = """You are the {knowledge_base} code analysis assistant.
Use the provided tools when code search, code explanation, or test generation is needed.
Never imitate a tool call or fabricate a tool result in message text. Treat tool results as the only source of code evidence.
Make at most one tool call per turn. After receiving sufficient search results, answer directly instead of making another tool call.
Answer in Chinese, concisely and accurately."""


def build_system_prompt(knowledge_base: str) -> str:
    return FUNCTION_CALLING_SYSTEM_PROMPT.format(knowledge_base=knowledge_base)
```

### 这段代码解决什么问题

这是 Agent 的"操作手册"——告诉 LLM 它是个代码助手、有哪些工具、按什么格式工作、有哪些规矩。

**相比早期版本（ReAct 的"思考-行动-观察"长模板 + few-shot 示例），现在大幅简化了**。原因是 Agent 从手写 JSON 解析升级成了**原生 tool-calling**：

- 早期：LLM 必须按模板输出 Action JSON → 系统从文本里解析。所以提示词要花大篇幅教格式、给示例。
- 现在：LLM 通过 `tools` 参数原生返回结构化 `tool_calls`。**格式约定由协议层保证，不需要在提示词里教**。提示词只剩三件事：身份、什么时候用工具、规则。

### 关键代码逐句拆解

**① `build_system_prompt(knowledge_base)` — 按知识库动态生成**

```python
def build_system_prompt(knowledge_base: str) -> str:
    return FUNCTION_CALLING_SYSTEM_PROMPT.format(knowledge_base=knowledge_base)
```

提示词里 `{knowledge_base}` 占位符被替换成知识库名（`TinyDB` / `Code Assistant Agent`）。**每个知识库的 Agent 提示词自动带上自己的名字**——多知识库场景下，模型知道自己在分析哪个库。

**② 规则部分 — 防幻觉**

```
Never imitate a tool call or fabricate a tool result in message text.
Treat tool results as the only source of code evidence.
```

两条核心规则：
- **不要模仿工具调用或编造工具结果**——防幻觉，答案必须基于真实检索结果。
- **工具结果是代码证据的唯一来源**——强制 LLM 基于 Observation 作答。

**③ 为什么不需要 few-shot 和 Action JSON 模板了？**

早期版本需要教 LLM "行动: {"name": "search", ...}" 的格式，因为系统要从文本里抠 JSON。现在 `tools` 参数让模型**结构化返回** tool_calls，格式由协议保证，提示词自然精简。这是 tool-calling 相比手写 ReAct 的"去提示词负担"。

### 面试答题要点

> **Q：为什么这个项目从 ReAct 提示词改成 tool-calling 后，提示词变短了？**
> 答：因为格式约定从"提示词里教"变成了"协议层保证"。原生 tool-calling 让模型结构化返回 tool_calls，不需要再教它输出 Action JSON，也不用 few-shot 示例。提示词只需要管身份和规则。

> **Q：提示词里的 {knowledge_base} 是干嘛的？**
> 答：多知识库支持。Agent 按知识库生成提示词，模型知道自己在分析 TinyDB 还是项目自身源码。

> **Q：规则里"不要编造工具结果"想防什么？**
> 答：防 LLM 幻觉。LLM 可能在没检索的情况下自己"脑补"代码库内容。规则强制它基于工具返回（Observation）作答，这是 RAG 防幻觉的核心。

> **Q：新增一个工具要改什么？**
> 答：只需在 tools.py 加一个继承 Tool 的类，定义 name / description / args_model（Pydantic 参数模型）/ execute。`function_schema()` 自动生成给 LLM 的 JSON Schema，harness 的 tool_map 自动注册，请求体的 tools 数组自动带上新工具。这是"开闭原则"——对扩展开放、对修改关闭。

---

## 5.4 tools.py — 三个 RAG 工具

### 完整代码

```python
"""Allow-listed tools bound to one public code knowledge base."""

from pydantic import BaseModel, Field

from app.agent.llm import call_llm
from app.agent.tool_base import Tool
from app.config import settings
from app.rag.dense_retriever import DenseRetriever, SYSTEM_CORPUS
from app.rag.fusion import rrf
from app.rag.knowledge_bases import DEFAULT_KNOWLEDGE_BASE, get_knowledge_base
from app.rag.sparse_retriever import SparseRetriever


class SearchArgs(BaseModel):
    query: str = Field(min_length=1, max_length=300)


class TargetArgs(BaseModel):
    target: str = Field(min_length=1, max_length=120)


class CodeTool(Tool):
    def __init__(self, knowledge_base_id: str = DEFAULT_KNOWLEDGE_BASE):
        self.knowledge_base = get_knowledge_base(knowledge_base_id)
        self.last_citations: list[dict] = []

    def _dense_retriever(self) -> DenseRetriever:
        return DenseRetriever(collection_name=self.knowledge_base.collection_name)

    def _search(self, query: str, top_k: int) -> list[dict]:
        dense = self._dense_retriever()
        sparse = SparseRetriever.from_redis(self.knowledge_base.collection_name)
        dense_results = dense.search(query, k=top_k * 2, where=SYSTEM_CORPUS)
        sparse_results = sparse.search(query, k=top_k * 2)
        if dense_results and sparse_results:
            results = rrf([dense_results, sparse_results], top_n=top_k)
        else:
            results = (dense_results or sparse_results)[:top_k]
        self.last_citations = [
            {
                "source": result["source"],
                "excerpt": result["text"][:300],
            }
            for result in results
        ]
        return results


class SearchCode(CodeTool):
    name = "search"
    args_model = SearchArgs

    def __init__(self, knowledge_base_id: str = DEFAULT_KNOWLEDGE_BASE):
        super().__init__(knowledge_base_id)
        self.description = f"Search the {self.knowledge_base.label} codebase for code snippets."

    def execute(self, **kwargs) -> str:
        results = self._search(kwargs["query"], top_k=5)
        if not results:
            return "No results found."
        return "\n---\n".join(
            f"[{result['source']}]\n{result['text'][:300]}\n"
            for result in results
        )


class ExplainCode(CodeTool):
    name = "explain"
    args_model = TargetArgs

    def __init__(self, knowledge_base_id: str = DEFAULT_KNOWLEDGE_BASE):
        super().__init__(knowledge_base_id)
        self.description = f"Explain a function or class from the {self.knowledge_base.label} codebase."

    def execute(self, **kwargs) -> str:
        target = kwargs["target"]
        results = self._search(target, top_k=3)
        if not results:
            return f"Could not find code related to '{target}'."
        context = "\n\n".join(result["text"][:400] for result in results)
        return call_llm(
            f"Explain the role of '{target}' in this code:\n\n{context}",
            system_prompt="You are a Python code tutor. Answer concisely in Chinese.",
            max_retries=0,
            timeout_seconds=settings.AGENT_TOOL_LLM_TIMEOUT_SECONDS,
        )


class GenerateTest(CodeTool):
    name = "testgen"
    args_model = TargetArgs

    def __init__(self, knowledge_base_id: str = DEFAULT_KNOWLEDGE_BASE):
        super().__init__(knowledge_base_id)
        self.description = f"Generate pytest tests for a function or class from the {self.knowledge_base.label} codebase."

    def execute(self, **kwargs) -> str:
        target = kwargs["target"]
        results = self._search(target, top_k=3)
        if not results:
            return f"Could not find code related to '{target}'."
        context = "\n\n".join(result["text"][:500] for result in results)
        return call_llm(
            f"Write pytest tests for '{target}' in the code below:\n\n{context}\n\nOutput code only.",
            system_prompt="You are a Python test engineer. Output runnable pytest code only.",
            max_retries=0,
            timeout_seconds=settings.AGENT_TOOL_LLM_TIMEOUT_SECONDS,
        )


def build_tools(knowledge_base_id: str = DEFAULT_KNOWLEDGE_BASE) -> list[Tool]:
    return [
        SearchCode(knowledge_base_id),
        ExplainCode(knowledge_base_id),
        GenerateTest(knowledge_base_id),
    ]


AVAILABLE_TOOLS = build_tools()
```

### 这段代码解决什么问题

三个工具，覆盖 Agent 的核心能力：**搜代码（search）、解释代码（explain）、生成测试（testgen）**。每个工具都是"RAG 检索 + LLM 加工"的组合——检索到相关代码后，让 LLM 干加工活。

**相比早期版本的关键变化**：
- **参数用 Pydantic 模型声明**（`SearchArgs` / `TargetArgs`），而不是手写 dict——自动生成 schema、自动校验。
- **工具绑定知识库**：所有工具继承 `CodeTool`，构造时指定 `knowledge_base_id`，检索操作在对应的 collection 上做。
- **抽了公共基类 `CodeTool`**：把 `_dense_retriever()` / `_search()` 提到父类，三个工具共用同一套检索逻辑，消除重复。

### 关键代码逐句拆解

**① 参数模型 — 每个工具声明 args_model**

```python
class SearchArgs(BaseModel):
    query: str = Field(min_length=1, max_length=300)

class TargetArgs(BaseModel):
    target: str = Field(min_length=1, max_length=120)
```

Pydantic 模型声明参数：`min_length` / `max_length` 限制长度。`function_schema()` 用 `model_json_schema()` 把它转成给 LLM 的 JSON Schema；`validate_args()` 在执行前校验。

**② `CodeTool` 公共基类 — 检索逻辑复用**

```python
class CodeTool(Tool):
    def __init__(self, knowledge_base_id=DEFAULT_KNOWLEDGE_BASE):
        self.knowledge_base = get_knowledge_base(knowledge_base_id)

    def _dense_retriever(self):
        return DenseRetriever(collection_name=self.knowledge_base.collection_name)

    def _search(self, query, top_k):
        dense = self._dense_retriever()
        sparse = SparseRetriever.from_redis(self.knowledge_base.collection_name)
        dense_results = dense.search(query, k=top_k * 2, where=SYSTEM_CORPUS)
        sparse_results = sparse.search(query, k=top_k * 2)
        if dense_results and sparse_results:
            return rrf([dense_results, sparse_results], top_n=top_k)
        return (dense_results or sparse_results)[:top_k]
```

- **知识库绑定**：构造时 `get_knowledge_base(knowledge_base_id)`，拿到 collection_name 和 label。`_dense_retriever` 用对应的 collection 建检索器。
- **`_search` 是统一混合检索**：dense（限定系统语料）+ sparse 各取 top_k×2，RRF 融合 top_k。两路都空时 `(dense_results or sparse_results)[:top_k]` 兜底。

**③ 工具 description 动态生成**

```python
def __init__(self, knowledge_base_id=DEFAULT_KNOWLEDGE_BASE):
    super().__init__(knowledge_base_id)
    self.description = f"Search the {self.knowledge_base.label} codebase for code snippets."
```

**每个工具的 description 带知识库名**——`Search the TinyDB codebase...` / `Search the Code Assistant Agent codebase...`。模型看到 description 就知道该工具作用于哪个库。

**④ `build_tools` — 工具工厂**

```python
def build_tools(knowledge_base_id=DEFAULT_KNOWLEDGE_BASE) -> list[Tool]:
    return [
        SearchCode(knowledge_base_id),
        ExplainCode(knowledge_base_id),
        GenerateTest(knowledge_base_id),
    ]

AVAILABLE_TOOLS = build_tools()   # 默认 tinydb 知识库
```

`build_tools(knowledge_base_id)` 按知识库构建一组工具。`AVAILABLE_TOOLS` 是默认（tinydb）的实例。AgentHarness 可以传入任意知识库的工具组。

### 面试答题要点

> **Q：Agent 工具内部为什么复用 RAG？**
> 答：工具就是"能力封装"。search 工具内部就是混合检索（dense + BM25 + RRF），explain/testgen 是"检索 + LLM 加工"。Agent 不重复实现检索，而是把 RAG 当作工具来调用——这正是"Agent 编排能力、RAG 提供能力"的分层。

> **Q：工具参数为什么用 Pydantic 模型？**
> 答：`args_model` 自动生成给 LLM 的 JSON Schema（`model_json_schema`），并在执行前校验参数（`model_validate`）——LLM 传的非法参数直接被拒，不会带脏数据执行工具。

> **Q：多知识库下工具怎么区分？**
> 答：工具绑定知识库。构造时传入 `knowledge_base_id`，description 自动带上知识库名，检索在对应的 collection 上做。`build_tools(kb_id)` 工厂按需生成一组工具。

> **Q：工具返回结果为什么是文本而不是结构化？**
> 答：因为 Observation 要放回消息列表给 LLM 看，文本是 LLM 最自然的输入。截断 300/400/500 字符控制 token 消耗。

---

## 5.5 harness.py — Tool-Calling 循环引擎（全项目核心）

### 完整代码

```python
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
```

### 这段代码解决什么问题

这是 **Agent 的核心循环引擎**。它把 tool-calling 的"模型决策 → 工具执行 → 结果回传"串起来，最多 `AGENT_MAX_STEPS`（默认 4）步，且有总时长预算：

```
① 系统提示词（按知识库）+ 历史 + 用户问题组装成 messages
② call_llm_with_tools（携带工具 schema）→ 结构化响应
③ 有 tool_calls → 逐个：校验参数 → 执行工具 → 把 tool 消息注入 → 回到②
④ 无 tool_calls → 认为 content 是最终答案 → 返回
⑤ 超过 max_step（6步）→ 返回"达到步数上限"
```

**相比早期版本（手写 ReAct + 括号深度解析 Action JSON）**，现在**不再需要自己从文本里解析 JSON**——LLM 通过 `tools` 参数原生返回结构化的 `tool_calls`。代码的重心从"解析"变成了"**校验 + 轨迹 + 防重复 + 预算控制 + 可观测**"。

### 关键代码逐句拆解

**① 构造函数 — 工具注入 + 知识库绑定 + 指标初始化**

```python
def __init__(self, tools=None, session_id="default", knowledge_base_id=DEFAULT_KNOWLEDGE_BASE):
    self.knowledge_base = get_knowledge_base(knowledge_base_id)
    if tools is None:
        from app.agent.tools import build_tools
        tools = build_tools(knowledge_base_id)   # 按知识库构建工具组
    self.tools = tools
    self.tool_map = {tool.name: tool for tool in self.tools}
    self.execution_trace = []
    self.metrics = {}      # 性能指标：协调 LLM 耗时/次数、工具耗时/次数
    ...
```

- **知识库绑定**：Agent 知道自己在分析哪个库，提示词带上库名。
- **工具注入**：外部可传自定义工具组（测试用），否则用 `build_tools(knowledge_base_id)` 按知识库构建。**延迟 import**（函数内 import）让协议测试和应用启动不依赖检索组件。
- **`metrics` 字典**：记录协调 LLM 耗时/调用次数、工具耗时/调用次数，供响应返回给前端展示（见 agent_router 的 `PerformanceMetrics`）。

**② `run` — 入口：初始化指标 + 委托 `_run`**

```python
def run(self, user_input, max_step=None, emit=None, stream_final=False, cancel_event=None) -> str:
    self.metrics = {
        "agent_latency_ms": 0.0,
        "coordinator_llm_latency_ms": 0.0,
        "tool_latency_ms": 0.0,
        "coordinator_llm_call_count": 0,
        "tool_call_count": 0,
    }
    started_at = monotonic()
    try:
        return self._run(user_input, max_step=max_step, emit=emit,
                         stream_final=stream_final, cancel_event=cancel_event)
    finally:
        self.metrics["agent_latency_ms"] = round((monotonic() - started_at) * 1000, 2)
```

`run` 是新版入口：初始化指标字典，用 `monotonic()`（单调时钟，不受系统时间调整影响）计时，最后在 `finally` 里填充总耗时。**新增参数**：
- `emit`：事件回调（`status` / `delta` / `trace`），用于 SSE 推送。
- `stream_final`：是否流式输出最终回答。
- `cancel_event`：客户端断开信号。

**②.5 `_run` — 主循环（预算控制）**

```python
max_step = min(max_step or settings.AGENT_MAX_STEPS, settings.AGENT_MAX_STEPS)
self._deadline = monotonic() + settings.AGENT_MAX_DURATION_SECONDS
for step in range(max_step):
    self._check_cancelled()
    remaining = self._deadline - monotonic()
    if remaining <= 0.2:
        return self._finish_from_observations(messages, user_input, step + 1, "已达到本轮时间预算")
    ...
    response = self._call_coordinator_llm(
        call_llm_with_tools, messages, self.get_tool_schemas(),
        max_retries=settings.AGENT_LLM_MAX_RETRIES,
        timeout_seconds=min(settings.AGENT_LLM_TIMEOUT_SECONDS, remaining),
        cancel_event=cancel_event,
    )
    if response is None:
        return self._finish_from_observations(messages, user_input, step + 1, "模型调用超时或暂时不可用")
```

**这是"受控执行"的核心**：
- **`_deadline`**：从启动开始算的总时长预算，每轮检查 `remaining`，超了就降级。
- **`_check_cancelled()`**：每步开头检查客户端是否断开，断开抛 `AgentCancelled`。
- **`_call_coordinator_llm`**：包装所有协调 LLM 调用，自动累计耗时和次数到 `metrics`。
- **LLM 调用超时 = `min(AGENT_LLM_TIMEOUT_SECONDS, remaining)`**——不超过总预算。
- **任何失败（超时/无响应）都不硬报错**，而是走 `_finish_from_observations` 用已有证据降级回答。

**②.6 降级回答 `_finish_from_observations` / `_fallback_answer`（亮点）**

```python
def _finish_from_observations(self, messages, user_input, step, reason, emit=None):
    remaining = self._deadline - monotonic()
    if remaining > 0.2:
        # 还有时间：让 LLM 基于已有 observation 做最后一次总结
        final_messages.append({"role": "user", "content": f"{reason} 现在必须停止调用工具...不要编造。"})
        answer = self._call_coordinator_llm(call_llm_with_messages, final_messages, ...)
        if answer.strip():
            return self._save_answer(user_input, answer.strip(), step, emit=emit)
    # 没时间了：直接给已有证据
    answer = self._fallback_answer(reason)
    return self._save_answer(user_input, answer, step, emit=emit)

def _fallback_answer(self, reason):
    observations = [item["observation"] for item in self.execution_trace
                    if item.get("status") == "completed" and item.get("observation")]
    if observations:
        return f"本轮已完成检索，但{reason}，未能生成完整归纳。以下是已获得的相关证据：\n{evidence}"
    return f"本轮处理未能完成：{reason}。请缩小问题范围后重试。"
```

**超预算/超时/模型无响应时，不是丢给用户一句"失败"**，而是：
1. 如果还有时间，让 LLM 基于已检索到的 `observation` 做最后一次总结（提示词明确"不要编造"）。
2. 没时间就直接把已获得的证据文本给用户。

这是"**优雅降级**"——用户至少拿到部分价值，而不是一个空错误。**这是面向工程化演示的可靠性措施（生产系统常见设计的基础实现）**。

**③ 工具执行 — 校验 + 状态分类 + 指标（亮点）**

```python
try:
    args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
    tool = self.tool_map.get(name)
    if tool is None:
        raise ValueError(f"Unknown tool '{name}'")
    trace_args = tool.validate_args(args)    # Pydantic 校验
    fingerprint = json.dumps({"name": name, "arguments": trace_args}, sort_keys=True)
    if fingerprint in executed_actions:      # 重复调用检测
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
    observation = self._tool_error(exc)      # 参数被拒
    status = "rejected"
except Exception:
    observation = json.dumps({"error": "Tool execution failed"})  # 执行崩溃
    status = "failed"
```

**三种失败状态**，各对应一种异常类型：
- `completed`：参数校验通过、执行成功。
- `rejected`：`ValidationError`（参数非法）/ `ValueError`（未知工具、重复调用）——**工具没执行**，错误作为 observation 告诉 LLM。
- `failed`：其他运行时异常——工具执行崩溃。

**`executed_actions` 指纹去重**：对 `(name, arguments)` 做确定性 JSON 指纹，已经执行过的工具调用直接拒绝——**这是防"LLM 反复调同一个工具死循环"的关键**。

**`finally` 块里的指标累计**：无论成功失败，工具耗时和次数都累计到 `metrics`——保证性能数据完整。

**③.5 citations — 引用来源（新）**

```python
citations = getattr(tool, "last_citations", []) if tool else []
if citations:
    trace["citations"] = citations
    self._merge_citations(citations)
```

工具执行后，从 `tool.last_citations`（tools.py 里检索时记录的来源）取出**引用**，写进轨迹，并合并到 `self.citations`。**这是 RAG 应用的"证据链"**——Agent 的每个回答都能追溯到具体代码来源，前端可以点开查看完整源码（配合 `/api/search/source`）。

**④ `execute_tool` — 返回结果 + 校验后参数**

```python
def execute_tool(self, name: str, args: dict) -> tuple[str, dict]:
    ...
    validated_args = tool.validate_args(args)
    result = tool.execute(**validated_args)
    return result, validated_args
```

返回**二元组**（结果文本, 校验后参数）——校验后参数用于轨迹记录（`arguments` 字段存的是干净参数，不是原始脏参数）。

**⑤ 执行轨迹 `execution_trace`**

```python
self.execution_trace.append({
    "step": step + 1,
    "tool_name": name or "invalid_tool_call",
    "arguments": trace_args,
    "status": status,
    "observation": observation[:200],
    "citations": citations,   # ← 新：该步的来源引用
})
```

每一步的工具执行摘要都记录到 `execution_trace`——这是**给前端展示的"执行轨迹"**（agent_router 返回给前端，Streamlit 渲染），也是可观测性的体现。**注意它不存完整思维链（chain of thought）**——只存工具名、参数、状态、观察摘要，避免暴露模型内部推理。

**⑥ `_schedule_log` — 异步日志的"上下文自适应"**

```python
def _schedule_log(self, **kwargs):
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        asyncio.run(self._log_step(**kwargs))     # 后台线程：没有事件循环
    else:
        loop.create_task(self._log_step(**kwargs))  # 有事件循环：create_task
```

Agent 可能在**两个地方**跑：API（FastAPI 异步上下文，有事件循环）→ `create_task`；脚本/测试（后台线程，没有事件循环）→ `asyncio.run`。`get_running_loop()` 探测后分别处理。

**⑦ 事件发射 `_emit` / `_check_cancelled`（新）**

```python
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
```

- `_emit`：统一的事件回调入口，安全包装（回调异常不影响主流程）。事件类型：`status`（进度）、`delta`（文本增量）、`trace`（工具轨迹）。
- `_check_cancelled`：**客户端断开检测**——SSE 连接消失时 `cancel_event` 置位，Agent 在下一次检查点抛 `AgentCancelled`，由路由捕获并通知"生成已取消"。

**⑧ 流式最终回答 `_finish_streaming_from_observations`（新）**

```python
def _finish_streaming_from_observations(self, messages, user_input, step, emit):
    def on_delta(text: str):
        parts.append(text)
        self._emit(emit, "delta", {"text": text})   # 实时推送增量给前端
    answer = self._call_coordinator_llm(
        call_llm_with_messages_stream, final_messages,
        on_delta=on_delta,
        timeout_seconds=min(settings.AGENT_LLM_TIMEOUT_SECONDS, remaining),
        cancel_event=self._cancel_event,
    ).strip()
```

当 `stream_final=True` 且有工具调用时，最终回答用**流式**生成——通过 `call_llm_with_messages_stream` 的 `on_delta` 回调，把每个 token 增量实时推给前端（SSE `delta` 事件），用户看到"打字机"效果，而不是等几十秒。同时完整答案会被拼接用于落库。

### 面试答题要点

> **Q：Tool-calling 循环怎么实现的？**
> 答：循环最多 N 步（`AGENT_MAX_STEPS`）。每轮把系统提示词 + 历史 + 当前问题组装成 messages，`call_llm_with_tools` 携带工具 schema 调 LLM；有 `tool_calls` 就逐个执行、把 tool 消息注入、continue；没有就取 content 当答案。**每步检查总时长预算（`_deadline`）和客户端断开信号**，超预算/断开就降级。

> **Q：原生 tool-calling 和手写 ReAct 解析 JSON 的区别？**
> 答：手写 ReAct 要自己写括号深度解析器从 LLM 文本里抠 Action JSON，还得处理格式错误；原生 tool-calling 让模型结构化返回 `tool_calls`（函数名 + 参数），格式由协议保证。代价是依赖服务商支持 tools 协议。**这个项目是从手写 ReAct 演进到 tool-calling 的**——先理解了原理，再用工业标准方案。

> **Q：怎么防止 LLM 反复调同一个工具？**
> 答：`executed_actions` 集合存 `(name, arguments)` 的确定性指纹，已执行过的调用直接拒绝，错误作为 observation 让 LLM 改用已有结果。这是防死循环的第一道防线；第二道是 `max_step` + `_deadline` 总预算。

> **Q：Agent 超时/超预算会怎样？**
> 答：不会硬报错。`_finish_from_observations` 先尝试让 LLM 基于已有 observation 做最后一次总结（提示词要求不编造）；没时间就直接把已获得的证据文本给用户。这是"优雅降级"——用户至少拿到部分价值。

> **Q：执行轨迹 execution_trace 和 agent_logs 的区别？**
> 答：`execution_trace` 是内存里的结构化列表（step/tool_name/arguments/status/observation/citations），返回给前端展示；`agent_logs` 是落库的决策摘要，供排查。两者都不存完整思维链，避免暴露模型内部推理。

> **Q：三种工具执行状态是什么？**
> 答：`completed`（校验通过并执行成功）、`rejected`（参数非法/未知工具/重复调用，工具没执行）、`failed`（运行时崩溃）。通过异常类型区分，每种都有对应的 observation 反馈给 LLM。

> **Q：citations（引用来源）是干嘛的？**
> 答：工具检索时记录命中的代码来源，Agent 回答能追溯到具体 `.py` 文件和片段。前端可以点开引用查看完整源码（走 `/api/search/source`）。这是 RAG 应用的"证据链"，回答可验证、可溯源。

> **Q：Agent 日志怎么做到异步不阻塞？**
> 答：`_schedule_log` 探测当前有无事件循环：有则 `loop.create_task`（不阻塞主循环），无则 `asyncio.run`（脚本场景）。

### 动手做

```bash
# 手动体验 Agent 循环（需 .env 配好 LLM_API_KEY）
cd backend
python -c "
from app.agent.harness import AgentHarness
h = AgentHarness()
ans = h.run('TinyDB 怎么把数据存到磁盘？')
print('ANSWER:', ans)
print('TRACE:', h.execution_trace)
"
```

---

### 第 5 层小结

Agent 层的核心思想：**把 LLM 当作决策者，工具当作执行器**。这个项目是从"手写 ReAct（LLM 输出 Action JSON + 括号深度解析）"**演进到"原生 tool-calling"**的——先理解了原理，再用工业标准方案。现在的核心是：

- **原生 tool-calling**：LLM 通过 `tools` 参数结构化返回 `tool_calls`，不用自己解析 JSON。
- **Pydantic 参数校验**：`args_model` 自动生成 schema + 执行前校验。
- **防重复调用**：`executed_actions` 指纹去重，杜绝死循环。
- **受控执行预算**：`max_step` + `_deadline` 总时长 + 单次 LLM 超时，超预算优雅降级。
- **执行轨迹**：`execution_trace` 记录每步状态（completed/rejected/failed），供前端展示和排查。
- **引用来源**：`citations` 让回答可溯源到具体代码。
- **性能指标**：`metrics` 记录协调 LLM / 工具耗时与次数。
- **流式输出**：`emit` 回调 + `_finish_streaming_from_observations` 支持 SSE 打字机效果。
- **取消机制**：`cancel_event` 客户端断开即中断。

面试讲 Agent，最有说服力的说法是："我先手写了一个 ReAct 循环理解原理，后来演进到原生 tool-calling，用 Pydantic 校验参数、指纹去重防死循环、deadline 做预算控制、citations 做引用溯源、SSE 做流式输出——同时支持客户端断开的取消。"——**既有原理深度，又有工业实践**。

---

## 5.6 eval_tasks.py — Agent 评测任务集（预留）

### 完整代码

```python
"""Agent 评测任务集"""

EVAL_TASKS = [
    {
        "question": "TinyDB 怎么把数据存到磁盘上的？",
        "reference": "TinyDB 使用 JSONStorage 类将数据以 JSON 格式存储在磁盘的单个文件中。每次写操作会序列化整个数据库并覆写文件。支持原子写入（临时文件 + os.replace）。",
        "description": "存储机制",
    },
    {
        "question": "请解释 TinyDB 中的 Query 类是怎么实现字段查询的？",
        "reference": "Query 类通过 __init__ 接收字段名，重载 __eq__、__lt__、__contains__ 等运算符生成条件表达式。多个条件通过 & 和 | 组合。每个 Query 实例表示一个查询条件。",
        "description": "查询机制",
    },
    {
        "question": "TinyDB 支持哪几种存储后端？分别有什么特点？",
        "reference": "TinyDB 支持 JSONStorage（JSON 文件存储，持久化）、MemoryStorage（内存存储，不持久化）。JSONStorage 是默认后端。",
        "description": "存储后端",
    },
    {
        "question": "TinyDB 的 insert 和 update 方法有什么区别？分别怎么用？",
        "reference": "insert 插入新文档并自动分配 _id。update 根据条件更新已有文档。insert 返回文档 ID，update 返回修改的文档数。",
        "description": "插入与更新",
    },
    {
        "question": "请帮我生成一段测试代码，测试 Table 类的 search 方法。",
        "reference": "生成的测试代码应该包含 pytest 函数，创建 TinyDB 实例，插入测试数据，调用 search 方法并断言结果符合预期。",
        "description": "测试生成",
    },
    {
        "question": "TinyDB 的中间件是怎么工作的？CachingMiddleware 有什么用？",
        "reference": "中间件包装存储层，在读写操作前后执行额外逻辑。CachingMiddleware 缓存写入请求，减少磁盘 I/O，需要手动 flush() 或 close() 才会实际写入。",
        "description": "中间件机制",
    },
    {
        "question": "解释一下 TinyDB 中 operations 模块里的 Increment 和 Delete 操作。",
        "reference": "Increment(field, value) 将指定字段增加 value。Delete(field) 删除文档中的指定字段。它们作为 update 方法的参数使用。",
        "description": "数据操作",
    },
    {
        "question": "TinyDB 是怎么保证并发安全的？多个进程同时写一个文件会怎样？",
        "reference": "TinyDB 默认不保证并发安全。多个进程同时写入可能导致数据损坏。JSONStorage 的原子写入只能防止单进程写入中断，不能防止多进程竞争。建议单进程使用或加外部锁。",
        "description": "并发安全",
    },
]
```

### 这段代码解决什么问题

这是 **Agent 评测任务集**——8 条"问题 + 参考答案 + 分类"，用来评估 Agent 的回答质量。它和 RAG 层的 `test_set.py`（评测检索）是一对：

- `test_set.py` → 评测**检索**好不好（答案是否命中正确文件）
- `eval_tasks.py` → 评测**Agent 回答**好不好（回答是否接近参考答案）

### 关键设计逐个讲

**① 结构：`question` + `reference` + `description`**

```python
{
    "question": "TinyDB 怎么把数据存到磁盘上的？",
    "reference": "TinyDB 使用 JSONStorage 类...",
    "description": "存储机制",
}
```

- `question`：问 Agent 的问题。
- `reference`：**参考答案**——评估时用某种文本相似度（如 ROUGE / LLM 打分）对比 Agent 的回答。
- `description`：问题分类，方便按主题统计。

**② 覆盖 Agent 的典型能力**

8 条任务覆盖了 Agent 应该会的几类事：存储机制、查询机制、API 使用（insert/update）、**测试生成**、中间件原理、并发安全——正好对应 `search` / `explain` / `testgen` 三个工具的场景。

### 重要说明：现在有配套评估脚本了

**`eval_tasks.py` 已被 `backend/scripts/eval_ragas.py` 引用**——它作为 **tinydb 知识库的 RAGAS 评测集**（`load_eval_tasks("tinydb")` 返回 `EVAL_TASKS`）。所以它已经从"预留数据"变成了**真实使用的评测数据**：

- tinydb 知识库 → 用 `eval_tasks.py` 的 8 条题
- project 知识库 → 用 `backend/data/eval/` 下的两个 JSON（34 条题）

配套脚本 `eval_ragas.py` 实现了完整的 RAGAS 评估链路：检索上下文 → LLM 生成回答 → Judge LLM 打分（`context_precision` / `answer_correctness`）。

### 面试答题要点

> **Q：怎么评估 Agent 的回答质量？**
> 答：我用 RAGAS 做端到端评估。`eval_tasks.py`（tinydb）+ `data/eval/`（project）提供带参考答案的评测集，`scripts/eval_ragas.py` 跑完整链路：生产检索链路取上下文 → LLM 基于上下文生成回答 → Judge LLM 算 `context_precision`（检索质量）和 `answer_correctness`（回答与参考答案的一致性）。**评估链路已跑通**；由于本地未保存完整原始输出且各轮有 judge 超时，对比分数（如不同 embedding）需重跑并记录题集版本、索引、Judge 与失败样本后才能引用（见评估记录）。

> **Q：Agent 评测和 RAG 检索评测有什么区别？**
> 答：检索评测（`test_set.py` + `evaluation.py`）看"检出来的文件对不对"，指标是 Hit Rate/MRR/NDCG；Agent 端到端评测（`eval_tasks.py` + `eval_ragas.py`）看"最终回答像不像参考答案 + 检索上下文是否有用"，指标是 RAGAS 的 context_precision / answer_correctness。一个是中间环节，一个是最终效果。

---

# 第 6 层 服务层

第 4、5 层的 RAG 和 Agent 是"能力"，但用户怎么用这些能力？需要一个**业务服务层**把它们串成具体的业务流程。这一层先看会话持久化服务，下一层看路由。

---

## 6.1 conversation_service.py — 会话持久化服务

### 完整代码

```python
"""会话持久化服务：Agent 对话历史的保存与恢复"""

from sqlalchemy import select

from app.database import async_session_factory
from app.models.conversation import Conversation, Message


async def get_or_create_conversation(user_id: int, session_id: str) -> Conversation:
    """获取或创建会话记录（按 user_id + session_id 隔离）"""
    async with async_session_factory() as session:
        result = await session.execute(
            select(Conversation).where(
                Conversation.user_id == user_id,
                Conversation.session_id == session_id,
            )
        )
        conv = result.scalar_one_or_none()
        if conv is None:
            conv = Conversation(user_id=user_id, session_id=session_id)
            session.add(conv)
            await session.commit()
            await session.refresh(conv)
        return conv


async def save_message(user_id: int, session_id: str, role: str, content: str, tool_calls=None):
    """保存一条消息（归属当前用户）"""
    async with async_session_factory() as session:
        session.add(Message(
            user_id=user_id,
            session_id=session_id,
            role=role,
            content=content,
            tool_calls=tool_calls,
        ))
        await session.commit()


async def load_history(user_id: int, session_id: str, limit: int = 20) -> list[dict]:
    """加载会话历史消息（按 user_id 过滤），返回 [{role, content}, ...]"""
    async with async_session_factory() as session:
        result = await session.execute(
            select(Message)
            .where(
                Message.user_id == user_id,
                Message.session_id == session_id,
            )
            .order_by(Message.created_at.asc())
            .limit(limit)
        )
        messages = result.scalars().all()
        return [
            {"role": m.role, "content": m.content}
            for m in messages
        ]
```

### 这段代码解决什么问题

让 Agent 对话**跨请求持久化**。每次调用 `/api/agent/chat`，服务层负责：会话不存在就创建、消息存起来、下次对话把历史捞出来还给 Agent。三个函数，职责单一。

**注意：每个函数都带 `user_id` 过滤**——这是数据隔离在服务层的体现，用户 A 永远读不到用户 B 的消息。

### 关键代码逐句拆解

**① `get_or_create_conversation` — 先查后建**

```python
result = await session.execute(
    select(Conversation).where(
        Conversation.user_id == user_id,
        Conversation.session_id == session_id,
    )
)
conv = result.scalar_one_or_none()
if conv is None:
    conv = Conversation(user_id=user_id, session_id=session_id)
    session.add(conv)
    await session.commit()
    await session.refresh(conv)
return conv
```

- `scalar_one_or_none()`：正好一条返回它，没有返回 `None`（多于一条会报错——但前面模型层有 `UniqueConstraint(user_id, session_id)` 兜底，保证最多一条）。
- 不存在就创建，`commit` 后 `refresh` 拿回数据库生成的 `id`。
- **注意这里没有并发防护**：两个并发请求同时发现"不存在"，都走创建——靠数据库的唯一约束兜底，第二个会报错。这是"应用层乐观 + 数据库层兜底"的取舍。

**② `save_message` — 追加一条消息**

```python
session.add(Message(
    user_id=user_id, session_id=session_id,
    role=role, content=content, tool_calls=tool_calls,
))
await session.commit()
```

`tool_calls` 参数预留（当前路由没传，字段留空）。

**③ `load_history` — 按时间顺序加载最近 N 条**

```python
select(Message)
.where(Message.user_id == user_id, Message.session_id == session_id)
.order_by(Message.created_at.asc())
.limit(limit)
```

- `order_by(created_at.asc())`：时间正序，保证对话顺序。
- `.limit(limit)`：最多 20 条——**历史太长会撑爆上下文窗口**，截断是保护机制。
- 返回 `[{role, content}, ...]` 结构，正好是 Agent `restore_history` 需要的格式（`harness.conversation_history` 就是 `[{role, content}]` 列表）。

### 面试答题要点

> **Q：会话历史为什么存 MySQL 而不是内存？**
> 答：服务重启、多实例部署都需要共享状态。存数据库可持久化、可扩展。内存只适合单进程 demo。

> **Q：为什么加载历史要 limit？**
> 答：上下文窗口有限。20 条历史 + 当前问题太长会超出 LLM 的 max_tokens，或让响应变慢。截断历史是 RAG/Agent 系统的常见保护。

> **Q：`get_or_create` 并发会怎样？**
> 答：应用层"先查后建"存在竞态，但数据库唯一约束（user_id, session_id）兜底，重复创建会被拒。这是"应用层尽量优化 + 数据库层保证正确"的经典组合。

---

# 第 7 层 API 路由层

服务层串好了业务逻辑，路由层把它**暴露成 HTTP 接口**。FastAPI 的路由层就是"门口的接待员"：接住请求、做参数校验、调服务、返回响应。4 个路由文件对应 4 组接口。

---

## 7.1 auth_router.py — 认证接口

### 完整代码

```python
"""认证路由：注册、登录、刷新、登出"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.auth import blacklist_token,is_token_blacklisted

import datetime
from datetime import UTC

from app.database import get_db
from app.models.user import User
from app.auth import (
    hash_password, verify_password,
    create_access_token, create_refresh_token, decode_token,
    get_current_user,security
)

router = APIRouter(prefix="/auth" , tags=["auth"])


class RegisterRequest(BaseModel):
    username:str
    password:str

class LoginRequest(BaseModel):
    username:str
    password:str

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


@router.post("/register" , response_model=TokenResponse)
async def register(req: RegisterRequest , db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(User).where(User.username == req.username))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400 , detail="Username already exists")

    user = User(
        username = req.username,
        hashed_password = hash_password(req.password),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    return TokenResponse(
        access_token=create_access_token({"sub": user.username}),
        refresh_token=create_refresh_token({"sub": user.username}),
    )

@router.post("/login" , response_model=TokenResponse)
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):

    result = await db.execute(select(User).where(User.username == req.username))
    user = result.scalar_one_or_none()
    if not user or not verify_password(req.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    return TokenResponse(
        access_token=create_access_token({"sub": user.username}),
        refresh_token=create_refresh_token({"sub": user.username}),
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(refresh_token: str, db: AsyncSession = Depends(get_db)):
    payload = decode_token(refresh_token)
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid token type")

    username = payload.get("sub")
    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    return TokenResponse(
        access_token=create_access_token({"sub": user.username}),
        refresh_token=create_refresh_token({"sub": user.username}),
    )


@router.post("/logout")
async def logout(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    current_user: User = Depends(get_current_user),
):
    # 把 access token 加入黑名单，剩余有效期
    payload = decode_token(credentials.credentials)
    exp = payload.get("exp", 0)
    now = int(datetime.datetime.now(UTC).timestamp())
    remain = max(exp - now, 1)

    blacklist_token(credentials.credentials, remain)
    return {"message": "Logged out successfully"}
```

### 这段代码解决什么问题

注册、登录、刷新、登出四个接口，对应 auth.py 的能力。所有请求体 / 响应都用 Pydantic 模型校验。

### 关键代码逐句拆解

**① Pydantic 模型 — 请求/响应契约**

```python
class RegisterRequest(BaseModel):
    username: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
```

- 请求模型定义接口"要什么"；响应模型（`response_model=TokenResponse`）定义"返回什么"。FastAPI 自动做校验、序列化、生成 OpenAPI 文档。
- 前端传多了字段会被忽略，传少了类型不对会 422。

**② `register` — 注册**

```python
existing = await db.execute(select(User).where(User.username == req.username))
if existing.scalar_one_or_none():
    raise HTTPException(status_code=400, detail="Username already exists")

user = User(username=req.username, hashed_password=hash_password(req.password))
db.add(user)
await db.commit()
await db.refresh(user)

return TokenResponse(
    access_token=create_access_token({"sub": user.username}),
    refresh_token=create_refresh_token({"sub": user.username}),
)
```

- 先查重：用户名存在返回 400。
- **`hash_password` 只存哈希**，永不存明文。
- 注册成功**直接返回 token**（免登录），`sub` 存用户名。

**③ `login` — 登录**

```python
if not user or not verify_password(req.password, user.hashed_password):
    raise HTTPException(status_code=401, detail="Invalid credentials")
```

**用户不存在和密码错误返回同一个错误**（401 "Invalid credentials"）——防账号枚举（否则攻击者能探测"这个用户名是否存在"）。这是安全细节，面试常考。

**④ `refresh` — 刷新 token**

```python
payload = decode_token(refresh_token)
if payload.get("type") != "refresh":
    raise HTTPException(status_code=401, detail="Invalid token type")
```

**校验 `type == "refresh"`**：防止拿 access token 来换新 token。因为两种 token 都用同一个 `SECRET_KEY` 签的，都能 `decode_token` 成功，必须靠 `type` 区分。

**⑤ `logout` — 登出**

```python
payload = decode_token(credentials.credentials)
exp = payload.get("exp", 0)
now = int(datetime.datetime.now(UTC).timestamp())
remain = max(exp - now, 1)
blacklist_token(credentials.credentials, remain)
```

- 从 token 里读出过期时间 `exp`（Unix 秒）。
- `remain = exp - now`：剩余有效秒数，作为 Redis 黑名单的 TTL。
- `max(remain, 1)`：兜底，至少 1 秒（防止刚签发就登出导致 TTL 为 0）。
- `blacklist_token` 把 token 写进 Redis，剩余寿命到期自动清除。

### 面试答题要点

> **Q：为什么登录失败返回统一的"Invalid credentials"？**
> 答：防止账号枚举。如果"用户不存在"和"密码错误"返回不同信息，攻击者就能探测系统里有哪些用户名。统一错误信息是安全最佳实践。

> **Q：refresh 接口怎么防止 access token 冒充？**
> 答：两种 token 用同一密钥签发，都能验签。所以 payload 里加了 `type` 字段区分，refresh 接口校验 `type == "refresh"`，access token 不通过。

> **Q：登出是怎么实现的？**
> 答：JWT 无状态，无法主动作废。登出时把 access token 加入 Redis 黑名单，TTL = token 剩余有效期。每次鉴权先查黑名单。到期自动清除，不占空间。

> **Q：为什么注册/登录都返回 token？**
> 答：注册成功直接发 token，用户免去"注册完再登录"的步骤，体验更好。`sub` 字段存用户名，是 JWT 的标准声明。

---

## 7.2 agent_router.py — Agent 对话接口

### 完整代码

```python
"""Agent 对话接口"""

import asyncio
import json
import threading
import time
from typing import Literal
from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from app.agent.harness import AgentCancelled, AgentHarness
from app.models.user import User
from app.auth import get_current_user
from app.config import settings
from app.logger import log
from app.services.conversation_service import (
    get_or_create_conversation, save_message, load_history,
)
from app.rag.knowledge_bases import DEFAULT_KNOWLEDGE_BASE

router = APIRouter(prefix="/agent", tags=["agent"])


class ChatRequest(BaseModel):
    message: str
    session_id: str = Field(default="default", min_length=1, max_length=55)
    knowledge_base: Literal["tinydb", "project"] = DEFAULT_KNOWLEDGE_BASE


class TraceStep(BaseModel):
    step: int
    tool_name: str
    arguments: dict | None = None
    status: str
    observation: str | None = None
    citations: list[dict] = Field(default_factory=list)


class Citation(BaseModel):
    knowledge_base: Literal["tinydb", "project"]
    source: str
    excerpt: str


class PerformanceMetrics(BaseModel):
    server_e2e_latency_ms: float
    agent_latency_ms: float
    coordinator_llm_latency_ms: float
    tool_latency_ms: float
    coordinator_llm_call_count: int
    tool_call_count: int
    time_to_first_token_ms: float | None = None


class ChatResponse(BaseModel):
    answer: str
    session_id: str
    trace: list[TraceStep]
    citations: list[Citation] = Field(default_factory=list)
    metrics: PerformanceMetrics


def _sse_event(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _with_knowledge_base(citations: list[dict], knowledge_base: str) -> list[dict]:
    return [{"knowledge_base": knowledge_base, **citation} for citation in citations]


def _performance_metrics(
    harness: AgentHarness,
    started_at: float,
    time_to_first_token_ms: float | None = None,
) -> dict:
    agent_metrics = getattr(harness, "metrics", {})
    return {
        "server_e2e_latency_ms": round((time.perf_counter() - started_at) * 1000, 2),
        "agent_latency_ms": agent_metrics.get("agent_latency_ms", 0.0),
        "coordinator_llm_latency_ms": agent_metrics.get("coordinator_llm_latency_ms", 0.0),
        "tool_latency_ms": agent_metrics.get("tool_latency_ms", 0.0),
        "coordinator_llm_call_count": agent_metrics.get("coordinator_llm_call_count", 0),
        "tool_call_count": agent_metrics.get("tool_call_count", 0),
        "time_to_first_token_ms": time_to_first_token_ms,
    }


@router.post("/chat", response_model=ChatResponse)
async def chat(
    req: ChatRequest,
    current_user: User = Depends(get_current_user),
):
    started_at = time.perf_counter()
    user_id = current_user.id
    scoped_session_id = f"{req.knowledge_base}:{req.session_id}"

    # 1. 确保会话记录存在（按用户隔离）
    await get_or_create_conversation(user_id, scoped_session_id)

    # 2. 从 MySQL 恢复历史（只查当前用户的）
    history = await load_history(user_id, scoped_session_id)
    harness = AgentHarness(
        session_id=scoped_session_id,
        knowledge_base_id=req.knowledge_base,
    )
    harness.restore_history(history)

    # 3. 运行 Agent（带请求级超时）
    try:
        answer = await asyncio.wait_for(
            asyncio.to_thread(harness.run, req.message),
            timeout=settings.AGENT_REQUEST_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        answer = (
            "本轮处理超过服务时间预算，未能生成完整回答。"
            "请缩小问题范围后重试。"
        )

    # 4. 保存本轮消息（归属当前用户）
    await save_message(user_id, scoped_session_id, "user", req.message)
    await save_message(user_id, scoped_session_id, "assistant", answer)

    return ChatResponse(
        answer=answer,
        session_id=req.session_id,
        trace=harness.execution_trace,
        citations=_with_knowledge_base(harness.citations, req.knowledge_base),
        metrics=_performance_metrics(harness, started_at),
    )


@router.post("/chat/stream")
async def chat_stream(
    req: ChatRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
):
    started_at = time.perf_counter()
    first_token_at = None
    user_id = current_user.id
    scoped_session_id = f"{req.knowledge_base}:{req.session_id}"
    await get_or_create_conversation(user_id, scoped_session_id)
    history = await load_history(user_id, scoped_session_id)
    harness = AgentHarness(
        session_id=scoped_session_id,
        knowledge_base_id=req.knowledge_base,
    )
    harness.restore_history(history)

    loop = asyncio.get_running_loop()
    events = asyncio.Queue()
    cancel_event = threading.Event()

    def emit(event: str, data: dict):
        nonlocal first_token_at
        if event == "delta" and first_token_at is None:
            first_token_at = (time.perf_counter() - started_at) * 1000
        loop.call_soon_threadsafe(events.put_nowait, (event, data))

    async def run_agent():
        try:
            answer = await asyncio.to_thread(
                harness.run,
                req.message,
                emit=emit,
                stream_final=True,
                cancel_event=cancel_event,
            )
            await save_message(user_id, scoped_session_id, "user", req.message)
            await save_message(user_id, scoped_session_id, "assistant", answer)
            emit("done", {
                "session_id": req.session_id,
                "citations": _with_knowledge_base(harness.citations, req.knowledge_base),
                "metrics": _performance_metrics(harness, started_at, first_token_at),
            })
        except AgentCancelled:
            emit("cancelled", {"message": "生成已取消。"})
        except Exception:
            log.exception("Streaming agent execution failed")
            emit("error", {"message": "Agent 执行失败，请稍后重试。"})
        finally:
            loop.call_soon_threadsafe(events.put_nowait, None)

    task = asyncio.create_task(run_agent())

    async def event_stream():
        try:
            while True:
                if await request.is_disconnected():
                    cancel_event.set()
                    task.cancel()
                    break
                try:
                    event = await asyncio.wait_for(events.get(), timeout=0.25)
                except asyncio.TimeoutError:
                    continue
                if event is None:
                    break
                event_name, data = event
                yield _sse_event(event_name, data)
        finally:
            cancel_event.set()
            if not task.done():
                task.cancel()

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
```

### 这段代码解决什么问题

这是**用户问 Agent 问题的入口**。它把第 5、6 层串起来：会话管理 → 历史恢复 → Agent 运行 → 结果落库 → 返回执行轨迹 + 引用 + 性能指标。**并且提供普通对话和 SSE 流式对话两个端点**。

**相比早期版本的变化**：
- 请求多了 `knowledge_base` 参数（多知识库）。
- **`scoped_session_id = f"{knowledge_base}:{session_id}"`**——会话按知识库隔离。
- 响应多了 `trace` / `citations` / `metrics` 三个字段。
- 新增 `/chat/stream` SSE 流式端点。

### 关键代码逐句拆解

**① `current_user: User = Depends(get_current_user)`**

路由的第一个依赖就是鉴权。**没登录直接 401**，登录了 `current_user` 就是数据库里的 User 对象。

**② 会话隔离（scoped_session_id）**

```python
scoped_session_id = f"{req.knowledge_base}:{req.session_id}"
```

把知识库前缀拼进 session_id——**同一用户、不同知识库的对话存在不同会话**。用户在前端切知识库，历史不会串。

**③ 普通对话 — 带请求级超时**

```python
try:
    answer = await asyncio.wait_for(
        asyncio.to_thread(harness.run, req.message),
        timeout=settings.AGENT_REQUEST_TIMEOUT_SECONDS,
    )
except asyncio.TimeoutError:
    answer = "本轮处理超过服务时间预算，未能生成完整回答。请缩小问题范围后重试。"
```

- `asyncio.to_thread(harness.run, ...)`：Agent 内部是**同步**的 LLM 调用（httpx.post 阻塞），扔进线程池让出事件循环。
- **`asyncio.wait_for` 套一层总超时**：即使 Agent 内部预算失效，请求级超时兜底，超时返回友好提示而不是挂死。

**④ 响应结构 — trace + citations + metrics**

```python
return ChatResponse(
    answer=answer,
    session_id=req.session_id,
    trace=harness.execution_trace,      # 工具执行摘要
    citations=_with_knowledge_base(harness.citations, req.knowledge_base),  # 引用来源
    metrics=_performance_metrics(harness, started_at),                       # 性能指标
)
```

- `trace`：每步工具执行摘要（tool_name / arguments / status / observation），**返回给前端展示**，同时**不暴露思维链**。
- `citations`：`_with_knowledge_base` 给每条引用补上知识库字段（`{"knowledge_base": ..., "source": ..., "excerpt": ...}`）。
- `metrics`：`_performance_metrics` 组装服务端端到端耗时 + Agent 内部指标（协调 LLM/工具耗时与次数）。

**⑤ `/chat/stream` — SSE 流式对话（核心新增）**

```python
loop = asyncio.get_running_loop()
events = asyncio.Queue()
cancel_event = threading.Event()

def emit(event: str, data: dict):
    nonlocal first_token_at
    if event == "delta" and first_token_at is None:
        first_token_at = (time.perf_counter() - started_at) * 1000
    loop.call_soon_threadsafe(events.put_nowait, (event, data))
```

**线程安全的事件桥**：Agent 在**线程池**里跑（`asyncio.to_thread`），SSE 循环在**事件循环**里跑。`emit` 用 `loop.call_soon_threadsafe` 把事件安全地从线程塞进 `asyncio.Queue`。事件类型：
- `status`：进度提示（"正在处理第 N 步…"）
- `delta`：文本增量（打字机效果），首次到达时记录 `first_token_at`
- `trace`：工具轨迹
- `done`：完成（含 citations + metrics）
- `error` / `cancelled`：失败/取消

```python
async def run_agent():
    try:
        answer = await asyncio.to_thread(
            harness.run, req.message,
            emit=emit, stream_final=True, cancel_event=cancel_event,
        )
        await save_message(user_id, scoped_session_id, "user", req.message)
        await save_message(user_id, scoped_session_id, "assistant", answer)
        emit("done", {"session_id": ..., "citations": ..., "metrics": ...})
    except AgentCancelled:
        emit("cancelled", {"message": "生成已取消。"})
    except Exception:
        emit("error", {"message": "Agent 执行失败，请稍后重试。"})
    finally:
        loop.call_soon_threadsafe(events.put_nowait, None)
```

- `stream_final=True`：最终回答用流式生成（harness 的 `_finish_streaming_from_observations`）。
- `cancel_event`：传给 Agent，客户端断开时置位。
- 完成后异步落库（消息保存不阻塞流式）。
- **AgentCancelled / 异常都转成 SSE 事件**，前端能明确区分"取消"和"失败"。

```python
async def event_stream():
    while True:
        if await request.is_disconnected():
            cancel_event.set()
            task.cancel()
            break
        try:
            event = await asyncio.wait_for(events.get(), timeout=0.25)
        except asyncio.TimeoutError:
            continue
        if event is None:
            break
        event_name, data = event
        yield _sse_event(event_name, data)

return StreamingResponse(
    event_stream(),
    media_type="text/event-stream",
    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
)
```

- **`request.is_disconnected()`**：SSE 是长连接，客户端可能随时断开。每 0.25s 轮询检查，断开就 `cancel_event.set()` + `task.cancel()`——**及时释放资源**，Agent 里的 LLM 调用也会因为 cancel_event 而中断。
- `_sse_event` 把事件格式化成 `event: xxx\ndata: json\n\n` 的 SSE 协议。
- `X-Accel-Buffering: no`：告诉 Nginx 等反向代理不要缓冲 SSE 响应（否则流式失效）。

### 面试答题要点

> **Q：Agent 是同步的，怎么放进异步 FastAPI？**
> 答：`asyncio.to_thread(harness.run, ...)` 把同步的 Agent 循环（内部是阻塞的 httpx LLM 调用）扔进线程池，让出事件循环。否则一个请求等 LLM 回复几十秒，整个服务就卡死了。

> **Q：SSE 流式怎么实现？**
> 答：Agent 在线程池跑，通过 `emit` 回调（`loop.call_soon_threadsafe` 桥到 `asyncio.Queue`）把 status/delta/trace 事件喂给事件循环，`event_stream` 生成器逐条 yield 成 SSE 帧。`request.is_disconnected()` 检测客户端断开，`cancel_event` 让 Agent 及时中断。

> **Q：客户端断开怎么办？**
> 答：SSE 长连接轮询 `request.is_disconnected()`，断开就置 `cancel_event` + `task.cancel()`。Agent 内部的 `_check_cancelled` 会在下一个检查点抛 `AgentCancelled`，路由转成 SSE `cancelled` 事件通知前端。**不会留下僵尸任务**。

> **Q：citations 和 metrics 是什么？**
> 答：citations 是引用来源（知识库 + 源文件 + 片段），前端可点开查看完整源码；metrics 是性能指标（端到端耗时、Agent 耗时、协调 LLM/工具耗时与次数、首 token 时间）。都是单次请求的观测值，用于定位慢点，不是压测数据。

> **Q：多轮对话怎么实现？**
> 答：每个 `scoped_session_id`（知识库前缀 + session_id）对应一个会话。请求进来先 `load_history` 从 MySQL 恢复最近 20 条，`restore_history` 给 Agent，Agent 基于历史 + 新问题作答，再 `save_message` 存两轮。

> **Q：数据隔离怎么贯穿？**
> 答：所有查询都带 `user_id`。`get_or_create_conversation`、`load_history`、`save_message` 都以 `user_id + scoped_session_id` 为键。用户 A 传用户 B 的 session_id 也查不到 B 的历史。

---

## 7.3 search_router.py — 代码检索接口

### 完整代码

```python
"""代码检索接口"""

import asyncio
import time
from pathlib import Path
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.rag.dense_retriever import DenseRetriever, SYSTEM_CORPUS
from app.rag.sparse_retriever import SparseRetriever
from app.rag.fusion import rrf, async_hybrid_search
from app.rag.reranker import Reranker
from app.rag.query_rewriter import rewrite
from app.rag.knowledge_bases import (
    DEFAULT_KNOWLEDGE_BASE,
    get_knowledge_base,
)
from app.models.user import User
from app.auth import get_current_user

router = APIRouter(prefix="/search", tags=["search"])

class SearchRequest(BaseModel):
    query: str
    knowledge_base: Literal["tinydb", "project"] = DEFAULT_KNOWLEDGE_BASE
    top_k: int = 5
    use_hybrid: bool = True
    use_hyde: bool = False
    use_rerank: bool = False


class SearchResult(BaseModel):
    text: str
    source: str


class SearchResponse(BaseModel):
    query: str
    knowledge_base: str
    results: list[SearchResult]
    latency_ms: float


class SourceResponse(BaseModel):
    source: str
    content: str


def _resolve_source_file(repo_path: str, source: str) -> Path:
    """Resolve an indexed Python source file without allowing path traversal."""
    project_root = Path(__file__).resolve().parents[3]
    root = Path(repo_path)
    if not root.is_absolute():
        root = project_root / root
    root = root.resolve()

    requested = Path(source)
    if requested.is_absolute() or requested.suffix != ".py":
        raise HTTPException(status_code=400, detail="Invalid source path")

    file_path = (root / requested).resolve()
    try:
        relative_path = file_path.relative_to(root)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid source path") from exc

    excluded = {".git", ".pytest_cache", ".venv", "env", "venv", "__pycache__", "data", "tests"}
    if any(part in excluded for part in relative_path.parts):
        raise HTTPException(status_code=404, detail="Source file not found")
    return file_path


@router.get("/source", response_model=SourceResponse)
async def read_source(
    knowledge_base: Literal["tinydb", "project"],
    source: str,
    current_user: User = Depends(get_current_user),
):
    """Return a public indexed source file for the authenticated caller."""
    knowledge_base_config = get_knowledge_base(knowledge_base)
    file_path = _resolve_source_file(knowledge_base_config.repo_path, source)
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="Source file not found")

    try:
        content = file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=404, detail="Source file is not UTF-8")
    except OSError as exc:
        raise HTTPException(status_code=404, detail="Source file not found") from exc

    return SourceResponse(source=source, content=content)

@router.post("" , response_model=SearchResponse)
async def search(
    req: SearchRequest,
    current_user: User = Depends(get_current_user),
):
    started_at = time.perf_counter()
    query = req.query.strip()
    if not query:
        raise HTTPException(status_code=400 , detail="Query is empty")

    knowledge_base = get_knowledge_base(req.knowledge_base)
    dense = DenseRetriever(collection_name=knowledge_base.collection_name)
    sparse = SparseRetriever.from_redis(knowledge_base.collection_name)

    if req.use_hyde:
        query = await rewrite(query, strategy="hyde")

    if req.use_hybrid:
        # 复用已有的 async_hybrid_search（含日志打点），默认只搜系统语料
        fused = await async_hybrid_search(
            query, dense, sparse, top_n=req.top_k,
            dense_where=SYSTEM_CORPUS,
        )
    else:
        dense_results = await asyncio.to_thread(
            dense.search, query, req.top_k, SYSTEM_CORPUS
        )
        fused = dense_results

    if req.use_rerank and fused:
        reranker = Reranker()
        fused = await asyncio.to_thread(
            reranker.rerank, query, fused, req.top_k
        )

    return SearchResponse(
        query=req.query,
        knowledge_base=knowledge_base.id,
        results=[
            SearchResult(text=r["text"], source=r["source"])
            for r in fused
        ],
        latency_ms=round((time.perf_counter() - started_at) * 1000, 2),
    )
```

### 这段代码解决什么问题

暴露 RAG 检索能力，**每个组件都做成开关**，并支持**多知识库**：

| 参数 | 默认 | 作用 |
|------|------|------|
| `knowledge_base` | `tinydb` | 选知识库（tinydb / project） |
| `use_hybrid` | `True` | 是否走双路混合检索（否则只走稠密） |
| `use_hyde` | `False` | 是否先 HyDE 改写 |
| `use_rerank` | `False` | 是否 cross-encoder 重排 |

这样调用方可以自由组合，对比不同配置的检索效果。

### 关键代码逐句拆解

**① 按知识库建检索器**

```python
knowledge_base = get_knowledge_base(req.knowledge_base)
dense = DenseRetriever(collection_name=knowledge_base.collection_name)
sparse = SparseRetriever.from_redis(knowledge_base.collection_name)
```

**核心变化**：检索器现在按知识库的 collection 构建。`tinydb` → `system_code`，`project` → `project_code`。每个知识库有独立的稠密 + 稀疏索引。

**② 默认只搜系统语料**

```python
fused = await async_hybrid_search(
    query, dense, sparse, top_n=req.top_k,
    dense_where=SYSTEM_CORPUS,   # 只搜系统语料，不碰用户上传
)
```

`dense_where=SYSTEM_CORPUS`：检索范围限定为系统语料（`{"source_type": "system"}`）。**防止系统检索把用户上传的私有内容搜出来**——这是数据隔离在检索接口的落地。

**③ 组件开关的流水线**

```python
if req.use_hyde:
    query = await rewrite(query, strategy="hyde")

if req.use_hybrid:
    fused = await async_hybrid_search(...)
else:
    fused = dense 只走稠密

if req.use_rerank and fused:
    fused = reranker.rerank(...)
```

HyDE 改写 → 检索 → 重排，每步可开关。这就是"把 RAG 链路做成可插拔"。

**④ 同步调用用 to_thread 包裹**

```python
dense_results = await asyncio.to_thread(dense.search, query, req.top_k, SYSTEM_CORPUS)
fused = await asyncio.to_thread(reranker.rerank, query, fused, req.top_k)
```

Chroma 检索和重排模型推理都是同步阻塞的，扔线程池。只有 `async_hybrid_search` 是异步的（它内部已用 to_thread 了）。

**⑤ 真实延迟（修复点）**

```python
started_at = time.perf_counter()   # 路由开头
...
latency_ms=round((time.perf_counter() - started_at) * 1000, 2),
```

**`latency_ms` 从写死的 0.0 改成了真实耗时**——`time.perf_counter()` 是最高精度的计时器，测量从路由开始到响应构造完成的端到端耗时。**这是本轮修复之一**：早期版本写死 `0.0`，接口性能数据不可信。

**⑥ `/search/source` — 查看完整源码（新端点）**

```python
def _resolve_source_file(repo_path: str, source: str) -> Path:
    project_root = Path(__file__).resolve().parents[3]
    root = Path(repo_path)
    if not root.is_absolute():
        root = project_root / root
    root = root.resolve()
    requested = Path(source)
    if requested.is_absolute() or requested.suffix != ".py":
        raise HTTPException(status_code=400, detail="Invalid source path")
    file_path = (root / requested).resolve()
    try:
        relative_path = file_path.relative_to(root)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid source path") from exc
    excluded = {".git", ".pytest_cache", ".venv", "env", "venv", "__pycache__", "data", "tests"}
    if any(part in excluded for part in relative_path.parts):
        raise HTTPException(status_code=404, detail="Source file not found")
    return file_path

@router.get("/source", response_model=SourceResponse)
async def read_source(knowledge_base, source, current_user=Depends(get_current_user)):
    file_path = _resolve_source_file(knowledge_base_config.repo_path, source)
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="Source file not found")
    content = file_path.read_text(encoding="utf-8")
    return SourceResponse(source=source, content=content)
```

**这是前端"引用代码 → 查看完整源码"的后端**。当用户点开 citations 里的引用，前端调 `/search/source?knowledge_base=...&source=tinydb/storages.py` 拿到完整 `.py` 内容。

**关键——路径穿越防护**（安全细节）：
- 拒绝绝对路径（`requested.is_absolute()`）和非 `.py` 文件。
- **`file_path.relative_to(root)` 校验**：解析后的路径必须仍在知识库根目录内，否则抛异常——防止 `../../etc/passwd` 这类目录穿越。
- **排除目录黑名单**：`.git`、`env`、`tests`、`data` 等一律 404——防止读取索引排除的敏感目录。
- 只允许读 `utf-8`，乱码文件 404。

### 面试答题要点

> **Q：为什么检索接口要把组件做成开关？**
> 答：方便对比验证。前端/测试可以分别开 hybrid、HyDE、rerank，直观看到哪个配置结果更好。这和技术栈里的消融实验是一套思路。

> **Q：多知识库检索怎么实现？**
> 答：请求带 `knowledge_base` 参数，路由查 `get_knowledge_base` 拿到对应 collection，`DenseRetriever` 和 `SparseRetriever` 都按该 collection 构建。tinydb 和 project 的索引物理隔离。

> **Q：检索接口怎么保证不搜到用户私有内容？**
> 答：`dense_where=SYSTEM_CORPUS` 把检索范围限定在系统语料（source_type=system）。用户上传内容在独立的 `user_uploads` collection，检索接口根本不碰。

> **Q：`/search/source` 怎么防路径穿越？**
> 答：三道防线。拒绝绝对路径和非 `.py`；`relative_to(root)` 校验解析后的路径必须在知识库根目录内；排除目录黑名单（`.git`、`env`、`tests`、`data`）一律 404。这防止攻击者用 `../../` 读取服务器任意文件。

> **Q：latency_ms 怎么测的？**
> 答：用 `time.perf_counter()` 在路由开头和结尾各取一次，差值毫秒数。这是端到端耗时，包含改写、检索、可选重排的完整链路。

---

## 7.4 upload_router.py — 文件上传接口

### 完整代码

```python
"""文件上传接口"""

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from pydantic import BaseModel
from app.rag.user_upload import UserUploadIndex
from app.models.user import User
from app.auth import get_current_user
from pathlib import Path

router = APIRouter(prefix="/upload", tags=["upload"])

ALLOWED_EXTENSIONS = {".py", ".js", ".md", ".txt"}


class UploadSearchRequest(BaseModel):
    query: str
    top_k: int = 5


@router.post("")
async def upload_file(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}")

    content_bytes = await file.read()
    try:
        content = content_bytes.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="File must be UTF-8 encoded")

    uploader = UserUploadIndex()
    chunk_count = uploader.add_file(file.filename, content, owner_id=current_user.id)

    return {
        "filename": file.filename,
        "chunk_count": chunk_count,
        "message": "File indexed successfully",
    }


@router.post("/search")
async def search_upload(
    req: UploadSearchRequest,
    current_user: User = Depends(get_current_user),
):
    """只检索当前用户自己上传的内容（owner_id 隔离）"""
    query = req.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query is empty")

    uploader = UserUploadIndex()
    results = uploader.search(query, owner_id=current_user.id, k=req.top_k)

    return {
        "query": req.query,
        "results": [
            {"text": r["text"], "source": r["source"]}
            for r in results
        ],
    }
```

### 这段代码解决什么问题

用户上传自己的代码文件 → 索引进 Chroma → 只能搜自己的。这是"个人知识库"能力，也是数据隔离的完整闭环。

### 关键代码逐句拆解

**① 文件类型白名单**

```python
ALLOWED_EXTENSIONS = {".py", ".js", ".md", ".txt"}

ext = Path(file.filename).suffix.lower()
if ext not in ALLOWED_EXTENSIONS:
    raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}")
```

用**白名单**（允许什么）而不是黑名单（禁止什么）——安全实践。`.suffix.lower()` 取扩展名并小写，防 `Test.PY` 绕过。

**② 编码校验**

```python
content_bytes = await file.read()
try:
    content = content_bytes.decode("utf-8")
except UnicodeDecodeError:
    raise HTTPException(status_code=400, detail="File must be UTF-8 encoded")
```

索引前先解码，失败直接 400——防止二进制文件/乱码文件进入索引库。

**③ 上传即索引（owner 隔离）**

```python
uploader = UserUploadIndex()
chunk_count = uploader.add_file(file.filename, content, owner_id=current_user.id)
```

`add_file` 内部给每个 chunk 打 `source_type="user_upload"` + `owner_id=current_user.id`（见 4.8 节）。

**④ 检索自己的上传**

```python
results = uploader.search(query, owner_id=current_user.id, k=req.top_k)
```

`owner_id=current_user.id` 从当前登录用户取，**不信任前端传的 owner**——防止越权。UserUploadIndex.search 内部还有应用层兜底过滤（双重隔离）。

### 面试答题要点

> **Q：上传文件怎么防止越权检索？**
> 答：三处配合。① 索引时 chunk 打 `owner_id`；② 检索时 `owner_id` 从当前登录用户取（不信任前端参数）；③ UserUploadIndex.search 内部再做应用层兜底过滤（source 前缀 + owner_id 二次校验）。纵深防御。

> **Q：为什么用扩展名白名单？**
> 答：白名单比黑名单安全——只允许明确支持的类型，未知类型一律拒绝，避免恶意文件混入。`.suffix.lower()` 防大小写绕过。

---

### 第 6、7 层小结

服务层（conversation_service）把"会话"这个业务概念落地，路由层把能力暴露成 HTTP。四个路由各司其职：auth（身份）、agent（对话）、search（检索）、upload（上传）。**贯穿所有路由的三件事：鉴权依赖、数据隔离（user_id/owner_id）、异步不阻塞（to_thread）**。

---

# 第 8 层 入口与部署

前面 7 层把"能力"都做好了，这一层把它们**组装成可运行的系统**，并解决"怎么跑起来"的问题：

- `main.py` —— 应用入口，组装路由 + 生命周期
- `streamlit_app.py` —— 前端，人机交互
- `docker-compose.yml` —— 一键部署 4 个服务
- `Dockerfile` —— 后端/前端镜像构建
- `ci.yml` —— GitHub Actions 持续集成

---

## 8.1 main.py — 应用入口组装

### 完整代码

```python
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import settings
from app.database import engine, Base
from app.logger import log
from app.routers.auth_router import router as auth_router
from app.routers.agent_router import router as agent_router
from app.routers.search_router import router as search_router
from app.routers.upload_router import router as upload_router
from app.middleware import RateLimitMiddleware



@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("%s Starting up...", settings.APP_NAME)

    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        log.info("Tables created successfully")
    except Exception as e:
        log.warning("Failed to create tables (may already exist): %s", e)

    yield

    try:
        await engine.dispose()
        log.info("Connection closed")
    except Exception as e:
        log.warning("Error closing connection: %s", e)


app = FastAPI(title=settings.APP_NAME, lifespan=lifespan)
app.add_middleware(RateLimitMiddleware, rate_limit=60, window_seconds=60)
app.include_router(auth_router, prefix="/api")
app.include_router(agent_router, prefix="/api")
app.include_router(search_router, prefix="/api")
app.include_router(upload_router, prefix="/api")

@app.get("/")
async def root():
    return {"message": f"{settings.APP_NAME} is running!"}


@app.get("/health")
async def health():
    return {"status": "ok"}
```

### 这段代码解决什么问题

**组装一切**：创建 FastAPI 实例、注册中间件、挂载路由、管理生命周期（启动建表 / 关闭释放连接）。

### 关键代码逐句拆解

**① `lifespan` — 生命周期管理（FastAPI 现代写法）**

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时执行
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        log.info("Tables created successfully")
    except Exception as e:
        log.warning("Failed to create tables (may already exist): %s", e)

    yield   # ← 应用运行期间停在这里

    # 关闭时执行
    try:
        await engine.dispose()
        log.info("Connection closed")
    except Exception as e:
        log.warning("Error closing connection: %s", e)
```

`lifespan` 是异步上下文管理器，替代旧的 `@app.on_event("startup")`。三段结构：

- **yield 之前**：启动钩子——建表。
- **yield**：应用运行期间（一直停在这）。
- **yield 之后**：关闭钩子——释放连接池。

**建表的细节**：

```python
async with engine.begin() as conn:
    await conn.run_sync(Base.metadata.create_all)
```

- `engine.begin()` 开启事务。
- `conn.run_sync(...)`：因为 SQLAlchemy 的 DDL（建表）是同步 API，`run_sync` 把它包到异步连接里执行。
- `Base.metadata.create_all`：基于所有继承 `Base` 的模型建表。**为什么不会重复建？** `create_all` 默认 `checkfirst=True`，表已存在就跳过。`except` 捕获"表已存在"等错误，启动不崩溃。

**② 中间件注册**

```python
app.add_middleware(RateLimitMiddleware, rate_limit=60, window_seconds=60)
```

挂载限流中间件：**每个客户端 60 秒内最多 60 次 API 请求**。注意中间件在路由之前执行，所以所有请求先过限流。

**③ 路由挂载**

```python
app.include_router(auth_router, prefix="/api")
app.include_router(agent_router, prefix="/api")
app.include_router(search_router, prefix="/api")
app.include_router(upload_router, prefix="/api")
```

- 统一 `prefix="/api"`，加上各 router 自己的 `prefix`（`/auth`、`/agent`、`/search`、`/upload`），得到最终路径：
  - `/api/auth/register`、`/api/auth/login`、`/api/auth/refresh`、`/api/auth/logout`
  - `/api/agent/chat`
  - `/api/search`
  - `/api/upload`、`/api/upload/search`

**④ 健康检查接口**

```python
@app.get("/health")
async def health():
    return {"status": "ok"}
```

给 Docker / 负载均衡 / CI 探活用的。`/` 返回应用名，`/health` 返回 `{"status": "ok"}`。

### 面试答题要点

> **Q：FastAPI 的 lifespan 是什么？**
> 答：异步上下文管理器，yield 前是启动钩子、yield 后是关闭钩子。替代旧的 `on_event("startup"/"shutdown")`。这里启动时建表、关闭时释放连接池。

> **Q：Base.metadata.create_all 为什么不重复建表？**
> 答：create_all 默认 checkfirst=True，检查表是否已存在，存在就跳过。所以多次启动不会报错。

> **Q：中间件和路由的执行顺序？**
> 答：中间件在请求进入路由前执行。RateLimitMiddleware 的 dispatch 在 call_next 之前做限流检查，超限直接 429，否则 call_next 放行进入路由。

---

## 8.2 streamlit_app.py — Streamlit 前端

### 完整代码

```python
"""Streamlit 前端：登录、Agent 对话、检索和文件上传。"""

import json
import os
import uuid
from urllib.parse import quote

import requests
import streamlit as st


API_BASE = os.environ.get("API_BASE", "http://127.0.0.1:8000/api")
KNOWLEDGE_BASE_LABELS = {
    "tinydb": "TinyDB 开源项目",
    "project": "当前 Code Assistant Agent 项目",
}


if "access_token" not in st.session_state:
    st.session_state.access_token = None
if "refresh_token" not in st.session_state:
    st.session_state.refresh_token = None
if "chat_sessions" not in st.session_state:
    st.session_state.chat_sessions = {}


def auth_headers():
    return {"Authorization": f"Bearer {st.session_state.access_token}"}


def response_detail(response, fallback: str) -> str:
    try:
        detail = response.json().get("detail", fallback)
    except (ValueError, AttributeError):
        return fallback
    return detail if isinstance(detail, str) else fallback


def safe_post(*args, **kwargs):
    try:
        return requests.post(*args, **kwargs)
    except requests.RequestException:
        return None


def get_chat_session(knowledge_base: str) -> dict:
    if knowledge_base not in st.session_state.chat_sessions:
        st.session_state.chat_sessions[knowledge_base] = {
            "session_id": uuid.uuid4().hex[:16],
            "messages": [],
        }
    return st.session_state.chat_sessions[knowledge_base]


def render_execution_trace(trace: list[dict]):
    """Render tool execution summaries without exposing model reasoning."""
    if not trace:
        return

    status_labels = {
        "completed": "完成",
        "rejected": "参数被拒绝",
        "failed": "执行失败",
    }
    with st.expander("执行轨迹", expanded=False):
        for item in trace:
            status = status_labels.get(item["status"], item["status"])
            st.caption(f"步骤 {item['step']} · {item['tool_name']} · {status}")
            if item.get("arguments"):
                st.code(json.dumps(item["arguments"], ensure_ascii=False), language="json")
            if item.get("observation"):
                st.code(item["observation"], language="text")


st.sidebar.title("🔐 登录")
auth_mode = st.sidebar.radio("模式", ["登录", "注册"])

def render_citations(citations: list[dict], scope: str):
    if not citations:
        return

    with st.expander("引用代码", expanded=False):
        for index, citation in enumerate(citations):
            st.caption(citation["source"])
            st.code(citation["excerpt"], language="python")
            source_url = (
                f"{API_BASE}/search/source?knowledge_base="
                f"{quote(citation['knowledge_base'])}&source={quote(citation['source'])}"
            )
            if st.button("查看完整源码", key=f"source_{scope}_{index}"):
                try:
                    response = requests.get(source_url, headers=auth_headers(), timeout=15)
                    if response.status_code == 200:
                        st.code(response.json()["content"], language="python")
                    else:
                        st.error(response_detail(response, "读取源码失败"))
                except requests.RequestException as exc:
                    st.error(f"读取源码失败: {exc}")


def render_performance_metrics(metrics: dict):
    if not metrics:
        return

    st.caption(
        "服务端耗时 "
        f"{metrics['server_e2e_latency_ms']:.0f} ms | "
        f"Agent {metrics['agent_latency_ms']:.0f} ms | "
        f"工具 {metrics['tool_latency_ms']:.0f} ms"
    )
    if metrics.get("time_to_first_token_ms") is not None:
        st.caption(f"流式首 token {metrics['time_to_first_token_ms']:.0f} ms")


def iter_sse_events(response):
    event_name = "message"
    data = None
    for raw_line in response.iter_lines(decode_unicode=True):
        line = raw_line.strip() if raw_line else ""
        if line.startswith("event:"):
            event_name = line.removeprefix("event:").strip()
        elif line.startswith("data:"):
            try:
                data = json.loads(line.removeprefix("data:").strip())
            except json.JSONDecodeError:
                continue
        elif not line and data is not None:
            yield event_name, data
            event_name = "message"
            data = None


if st.session_state.access_token:
    st.sidebar.success("已登录")
    if st.sidebar.button("退出登录"):
        try:
            requests.post(f"{API_BASE}/auth/logout", headers=auth_headers())
        except Exception:
            pass
        st.session_state.access_token = None
        st.session_state.refresh_token = None
        st.session_state.chat_sessions = {}
        st.rerun()
else:
    username = st.sidebar.text_input("用户名")
    password = st.sidebar.text_input("密码", type="password")
    if st.sidebar.button("提交"):
        url = f"{API_BASE}/auth/login" if auth_mode == "登录" else f"{API_BASE}/auth/register"
        try:
            response = requests.post(
                url, json={"username": username, "password": password}, timeout=15
            )
            if response.status_code == 200:
                data = response.json()
                st.session_state.access_token = data["access_token"]
                st.session_state.refresh_token = data["refresh_token"]
                st.session_state.chat_sessions = {}
                st.sidebar.success("登录成功")
                st.rerun()
            else:
                st.sidebar.error(response_detail(response, "登录失败"))
        except (requests.RequestException, KeyError, ValueError):
            st.sidebar.error("无法连接后端，请确认服务已启动后重试。")


st.title("🤖 Code Assistant Agent")
st.caption("基于 TinyDB 与项目源码的代码检索助手")

if not st.session_state.access_token:
    st.info("请先在左侧登录或注册")
    st.stop()


tab_chat, tab_search, tab_upload = st.tabs(["💬 对话", "🔍 检索", "📁 上传"])

with tab_chat:
    chat_knowledge_base = st.selectbox(
        "对话知识库",
        options=list(KNOWLEDGE_BASE_LABELS),
        format_func=KNOWLEDGE_BASE_LABELS.__getitem__,
        key="chat_knowledge_base",
    )
    chat_session = get_chat_session(chat_knowledge_base)
    for message_index, message in enumerate(chat_session["messages"]):
        with st.chat_message(message["role"]):
            if message.get("failed"):
                st.error(message["content"])
            else:
                st.markdown(message["content"])
            if message["role"] == "assistant":
                render_execution_trace(message.get("trace", []))
                render_citations(message.get("citations", []), f"history_{message_index}")
                render_performance_metrics(message.get("metrics", {}))

    if prompt := st.chat_input("问代码库中的实现细节..."):
        chat_session["messages"].append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Agent 处理中..."):
                streamed = False
                failed = False
                citations = []
                metrics = {}
                trace = []
                answer = ""
                response = None
                try:
                    response = requests.post(
                        f"{API_BASE}/agent/chat/stream",
                        json={
                            "message": prompt,
                            "session_id": chat_session["session_id"],
                            "knowledge_base": chat_knowledge_base,
                        },
                        headers=auth_headers(),
                        timeout=90,
                        stream=True,
                    )
                    if response.status_code == 200:
                        streamed = True
                        answer_parts = []
                        answer_placeholder = st.empty()
                        status_placeholder = st.empty()
                        for event, data in iter_sse_events(response):
                            if event == "status":
                                status_placeholder.caption(data["message"])
                            elif event == "trace":
                                trace.append(data["trace"])
                            elif event == "delta":
                                answer_parts.append(data["text"])
                                answer_placeholder.markdown("".join(answer_parts))
                            elif event == "done":
                                citations = data.get("citations", [])
                                metrics = data.get("metrics", {})
                            elif event == "error":
                                answer = data.get("message", "Agent 执行失败")
                                failed = True
                                answer_placeholder.error(answer)
                                break
                            elif event == "cancelled":
                                answer = data.get("message", "生成已取消")
                                failed = True
                                status_placeholder.warning(answer)
                                break
                        status_placeholder.empty()
                        if not failed:
                            answer = "".join(answer_parts).strip()
                        if not failed and not answer:
                            answer = "Agent 未返回内容，请稍后重试。"
                            failed = True
                    else:
                        answer = response_detail(response, "Agent 请求失败")
                        failed = True
                except requests.Timeout:
                    answer = "请求等待时间过长，Agent 未能及时完成。请缩小问题范围后重试。"
                    failed = True
                except requests.RequestException as exc:
                    answer = f"请求失败: {exc}"
                    failed = True
                finally:
                    if response is not None:
                        response.close()
            if failed:
                st.error(answer)
            elif not streamed:
                st.markdown(answer)
            if not failed:
                render_execution_trace(trace)
                render_citations(citations, f"response_{len(chat_session['messages'])}")
                render_performance_metrics(metrics)
            if not failed:
                chat_session["messages"].append({
                    "role": "assistant",
                    "content": answer,
                    "trace": trace,
                    "citations": citations,
                    "metrics": metrics,
                })

with tab_search:
    search_knowledge_base = st.selectbox(
        "检索知识库",
        options=list(KNOWLEDGE_BASE_LABELS),
        format_func=KNOWLEDGE_BASE_LABELS.__getitem__,
        key="search_knowledge_base",
    )
    query = st.text_input("输入检索查询")
    top_k = st.slider("返回条数", 1, 10, 5)
    if st.button("检索") and query:
        response = safe_post(
            f"{API_BASE}/search",
            json={
                "query": query,
                "knowledge_base": search_knowledge_base,
                "top_k": top_k,
            },
            headers=auth_headers(),
            timeout=60,
        )
        if response is None:
            st.error("检索请求失败，请稍后重试。")
        elif response.status_code == 200:
            results = response.json()["results"]
            if not results:
                st.info("没有找到结果")
            for result in results:
                st.markdown(f"**{result['source']}**")
                st.code(result["text"][:300], language="python")
        else:
            st.error(response_detail(response, "检索失败"))

with tab_upload:
    uploaded = st.file_uploader("上传代码文件", type=["py", "js", "md", "txt"])
    if uploaded and st.button("上传并索引"):
        response = safe_post(
            f"{API_BASE}/upload",
            files={"file": (uploaded.name, uploaded.getvalue(), "text/plain")},
            headers=auth_headers(),
            timeout=60,
        )
        if response is None:
            st.error("上传请求失败，请稍后重试。")
        elif response.status_code == 200:
            st.success(f"索引成功: {response.json()['chunk_count']} chunks")
        else:
            st.error(response_detail(response, "上传失败"))

    upload_query = st.text_input("查询自己上传的内容")
    if st.button("检索上传内容") and upload_query:
        response = safe_post(
            f"{API_BASE}/upload/search",
            json={"query": upload_query, "top_k": 5},
            headers=auth_headers(),
            timeout=60,
        )
        if response is None:
            st.error("检索请求失败，请稍后重试。")
        elif response.status_code == 200:
            results = response.json()["results"]
            if not results:
                st.info("没有找到结果")
            for result in results:
                st.markdown(f"**{result['source']}**")
                st.code(result["text"][:300], language="python")
        else:
            st.error(response_detail(response, "检索失败"))
```

### 这段代码解决什么问题

一个**纯前端页面**（Streamlit），用 `requests` 调后端 API。用户在这里登录、和 Agent 对话、检索代码、上传文件。不涉及任何后端逻辑——它只是"后端的遥控器"。

**相比早期版本的变化**：
- **多知识库选择**：对话和检索 Tab 都有知识库下拉框（tinydb / project）。
- **流式对话**：对话 Tab 用 `/agent/chat/stream` 的 SSE 流式，实时展示"打字机"效果。
- **执行轨迹 / 引用 / 指标展示**：回答下方有执行轨迹、引用代码、性能指标三个区域。
- **完整失败态**：网络失败、超时、服务端错误、取消都有明确的用户提示。
- **上传检索独立**：上传 Tab 不仅能传文件，还能查自己上传的内容。

### 关键代码逐句拆解

**① `st.session_state` — 页面级状态**

```python
if "access_token" not in st.session_state:
    st.session_state.access_token = None
if "chat_sessions" not in st.session_state:
    st.session_state.chat_sessions = {}
```

Streamlit 每次交互会重跑整个脚本，所以状态必须存 `st.session_state`（否则刷新就丢）。**`chat_sessions` 是 key 为知识库名的 dict**——每个知识库有独立的会话（session_id + messages），切知识库不串历史。

**② `get_chat_session` — 按知识库建会话**

```python
def get_chat_session(knowledge_base: str) -> dict:
    if knowledge_base not in st.session_state.chat_sessions:
        st.session_state.chat_sessions[knowledge_base] = {
            "session_id": uuid.uuid4().hex[:16],
            "messages": [],
        }
    return st.session_state.chat_sessions[knowledge_base]
```

每个知识库独立 session_id（`uuid.uuid4().hex[:16]`）——防止跨知识库/跨用户历史共享。

**③ 三个渲染辅助函数**

```python
def render_execution_trace(trace):   # 执行轨迹折叠面板
    status_labels = {"completed": "完成", "rejected": "参数被拒绝", "failed": "执行失败"}
    with st.expander("执行轨迹", expanded=False):
        for item in trace:
            st.caption(f"步骤 {item['step']} · {item['tool_name']} · {status}")

def render_citations(citations, scope):   # 引用代码折叠面板
    with st.expander("引用代码", expanded=False):
        for index, citation in enumerate(citations):
            st.code(citation["excerpt"], language="python")
            if st.button("查看完整源码", key=f"source_{scope}_{index}"):
                response = requests.get(source_url, headers=auth_headers(), timeout=15)
                if response.status_code == 200:
                    st.code(response.json()["content"], language="python")

def render_performance_metrics(metrics):  # 性能指标
    st.caption("服务端耗时 X ms | Agent Y ms | 工具 Z ms")
```

- `render_execution_trace`：每步工具名、状态（完成/参数被拒/失败）、参数、观察——可观测性的前端体现，不暴露思维链。
- `render_citations`：**引用代码**——展示每条引用的片段，点"查看完整源码"调 `/search/source?knowledge_base=...&source=...`（用 `quote` 编码 URL 参数）拿完整 `.py` 展示。
- `render_performance_metrics`：展示端到端耗时、Agent 耗时、工具耗时，流式还有首 token 时间。

**④ `iter_sse_events` — SSE 流解析**

```python
def iter_sse_events(response):
    event_name = "message"
    data = None
    for raw_line in response.iter_lines(decode_unicode=True):
        line = raw_line.strip() if raw_line else ""
        if line.startswith("event:"):
            event_name = line.removeprefix("event:").strip()
        elif line.startswith("data:"):
            data = json.loads(line.removeprefix("data:").strip())
        elif not line and data is not None:   # 空行 = 事件结束
            yield event_name, data
            event_name = "message"
            data = None
```

SSE 协议按行解析：`event:` 行定事件名，`data:` 行是 JSON 数据，**空行表示一个事件结束**。这个生成器把后端的 SSE 流转成 `(event_name, data)` 元组序列。

**⑤ 对话 Tab — 流式对话（核心）**

```python
response = requests.post(
    f"{API_BASE}/agent/chat/stream",
    json={"message": prompt, "session_id": ..., "knowledge_base": ...},
    headers=auth_headers(),
    timeout=90,
    stream=True,
)
if response.status_code == 200:
    answer_parts = []
    answer_placeholder = st.empty()
    status_placeholder = st.empty()
    for event, data in iter_sse_events(response):
        if event == "status":
            status_placeholder.caption(data["message"])      # 进度提示
        elif event == "trace":
            trace.append(data["trace"])                        # 工具轨迹
        elif event == "delta":
            answer_parts.append(data["text"])                  # 文本增量
            answer_placeholder.markdown("".join(answer_parts)) # 实时刷新
        elif event == "done":
            citations = data.get("citations", [])
            metrics = data.get("metrics", {})
        elif event == "error":
            failed = True; answer_placeholder.error(...)
        elif event == "cancelled":
            failed = True; status_placeholder.warning(...)
```

**流式对话的关键**：
- `stream=True` 让 requests 不一次性读完整响应，而是逐块读。
- 收到 `delta` 事件就实时 `markdown` 更新——**用户看到"打字机"效果**，而不是等几十秒。
- `status`（进度）、`trace`（轨迹）、`done`（最终引用 + 指标）各司其职。
- `error` / `cancelled` 明确区分失败和取消。

**完整失败态**：请求超时（`requests.Timeout`）、网络异常（`RequestException`）、非 200、服务端 error 事件、cancelled 事件、Agent 空回答——每种都有明确的中文提示，不会让用户看到空白或崩溃。

**⑥ 检索 Tab — 带知识库 + safe_post**

```python
def safe_post(*args, **kwargs):
    try:
        return requests.post(*args, **kwargs)
    except requests.RequestException:
        return None
...
response = safe_post(f"{API_BASE}/search", json={...}, headers=auth_headers(), timeout=60)
if response is None:
    st.error("检索请求失败，请稍后重试。")
```

`safe_post` 把网络异常转成 `None`，调用方统一处理——避免 `try/except` 散落各处。

**⑦ 上传 Tab — 上传 + 检索**

```python
files={"file": (uploaded.name, uploaded.getvalue(), "text/plain")}
requests.post(f"{API_BASE}/upload/search", json={"query": upload_query, "top_k": 5}, ...)
```

`requests` 的 multipart 上传格式：`{"file": (文件名, 内容, MIME类型)}`。上传 Tab 还加了"检索上传内容"输入框，调 `/upload/search` 查自己上传的。

### 面试答题要点

> **Q：前端怎么和后端通信？**
> 答：Streamlit 页面用 `requests` 调后端 REST API，token 放 `Authorization` 头。对话用 SSE 流式（`/chat/stream`），检索/上传用普通 POST。前后端通过 HTTP + JWT 解耦。

> **Q：为什么每个知识库一个 session_id？**
> 答：防止跨知识库/跨用户历史共享。`chat_sessions` 以知识库为 key，每个知识库独立 session_id，切换知识库不串历史，配合后端 `user_id + scoped_session_id` 隔离。

> **Q：SSE 流式在前端怎么解析？**
> 答：`iter_sse_events` 按行解析 `event:` / `data:` 前缀，空行表示事件结束。收到 `delta` 事件就实时 `markdown` 更新（打字机效果），`status`/`trace`/`done`/`error`/`cancelled` 各司其职。

> **Q：前端怎么展示引用？**
> 答：`render_citations` 折叠面板展示引用片段，点"查看完整源码"调 `/search/source` 拿完整 `.py`。这样 Agent 的每个回答都能追溯到具体代码。

> **Q：为什么对话请求超时设 90 秒？**
> 答：Agent 有 `AGENT_MAX_STEPS` + `AGENT_MAX_DURATION_SECONDS` 预算（默认 75s），请求级超时 `AGENT_REQUEST_TIMEOUT_SECONDS` 兜底。前端超时设 90s 略大于服务端预算，避免前端先断开。普通 HTTP 默认超时太短，会提前断开。

---

## 8.3 docker-compose.yml — 一键部署

### 完整代码

```yaml
# version:  "3.8"

services:
  mysql:
    image: mysql:8.0
    environment:
      MYSQL_ROOT_PASSWORD: 123456
      MYSQL_DATABASE: code_assistant
    ports:
      - "3306:3306"
    volumes:
      - mysql_data:/var/lib/mysql
    healthcheck:
      test: ["CMD", "mysqladmin", "ping", "-h", "localhost"]
      interval: 5s
      timeout: 3s
      retries: 10

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 10

  backend:
    build: ./backend
    ports:
      - "8000:8000"
    environment:
      MYSQL_HOST: mysql
      MYSQL_PORT: 3306
      MYSQL_USER: root
      MYSQL_PASSWORD: 123456
      MYSQL_DATABASE: code_assistant
      REDIS_HOST: redis
      REDIS_PORT: 6379
      LLM_API_KEY: ${LLM_API_KEY}
      JWT_SECRET: ${JWT_SECRET}
      REPO_PATH: /workspace/project/data/target_repo
      PROJECT_SOURCE_PATH: /workspace/project
    volumes:
      - ./:/workspace/project:ro
    depends_on:
      mysql:
        condition: service_healthy
      redis:
        condition: service_healthy

  frontend:
    build: ./frontend
    ports:
      - "8501:8501"
    environment:
      API_BASE: http://backend:8000/api
    depends_on:
      - backend

volumes:
  mysql_data:
```

### 这段代码解决什么问题

**一个命令跑起整个系统**：`docker compose up --build` 启动 4 个服务（MySQL、Redis、backend、frontend）。网络、依赖、健康检查都在一个文件里声明。

### 关键代码逐句拆解

**① MySQL / Redis — 基础设施**

```yaml
mysql:
  image: mysql:8.0
  environment:
    MYSQL_ROOT_PASSWORD: 123456
    MYSQL_DATABASE: code_assistant
  volumes:
    - mysql_data:/var/lib/mysql
```

- 声明式配置：root 密码、默认数据库名。
- `volumes` 挂载命名卷，**数据持久化**——容器重启不丢数据。

**② healthcheck — 健康检查（关键设计）**

```yaml
healthcheck:
  test: ["CMD", "mysqladmin", "ping", "-h", "localhost"]
  interval: 5s
  timeout: 3s
  retries: 10
```

MySQL 和 Redis 都加了健康检查。**为什么必须有？** 因为 backend 依赖数据库，如果没等 MySQL 就绪就启动后端，连接会失败。

**③ depends_on + condition: service_healthy — 依赖就绪才启动**

```yaml
backend:
  depends_on:
    mysql:
      condition: service_healthy
    redis:
      condition: service_healthy
```

- `depends_on`：指定依赖关系。
- **`condition: service_healthy`**：只有依赖服务通过健康检查后才启动 backend。这比"sleep 10 秒"靠谱——等的是"真正就绪"而不是"时间到了"。

**④ 环境变量透传 — 密钥不进文件**

```yaml
backend:
  environment:
    ...
    LLM_API_KEY: ${LLM_API_KEY}
    JWT_SECRET: ${JWT_SECRET}
```

`${LLM_API_KEY}` 从**宿主机的 .env 文件**读入（compose 自动加载同目录 `.env`），**密钥不进 docker-compose.yml 仓库**。这是密钥管理的延续。

**④.5 挂载项目源码 — 支撑 project 知识库**

```yaml
environment:
  REPO_PATH: /workspace/project/data/target_repo   # tinydb 知识库路径（容器内）
  PROJECT_SOURCE_PATH: /workspace/project          # project 知识库路径（容器内）
volumes:
  - ./:/workspace/project:ro                       # 只读挂载
```

**这是多知识库的部署关键**：容器里 `project` 知识库要索引的是"项目自身源码"，所以把整个项目目录**只读挂载**进容器（`./:/workspace/project:ro`）。`ro`（read-only）保证容器只能读、不能改宿主代码。同时 `REPO_PATH` / `PROJECT_SOURCE_PATH` 指向容器内的路径——`config.py` 里的 `PROJECT_SOURCE_PATH` 就是为这个设计的。

**⑤ 服务间通信用服务名**

```yaml
frontend:
  environment:
    API_BASE: http://backend:8000/api
```

Compose 网络里，`backend` 是主机名。前端容器访问后端直接 `http://backend:8000`，不用 IP。

### 面试答题要点

> **Q：为什么用 condition: service_healthy？**
> 答：`depends_on` 默认只保证"容器启动"，不保证"服务就绪"。MySQL 容器起来但没初始化完，后端连数据库会失败。healthcheck + `condition: service_healthy` 保证依赖真正可用才启动。

> **Q：密钥怎么不写进 compose 文件？**
> 答：`${LLM_API_KEY}` 引用宿主机的环境变量（compose 自动读同目录 `.env`）。密钥只存在于宿主机 `.env`，不进版本库。

> **Q：MySQL 数据怎么持久化？**
> 答：命名卷 `mysql_data` 挂到 `/var/lib/mysql`。容器删了重建，数据还在。

---

## 8.4 Dockerfile — 后端与前端镜像

### 完整代码

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# 换用国内 apt 源（阿里云），加速系统依赖安装
RUN sed -i 's|deb.debian.org|mirrors.aliyun.com|g' /etc/apt/sources.list.d/debian.sources \
    && sed -i 's|deb.debian.org|mirrors.aliyun.com|g' /etc/apt/sources.list 2>/dev/null || true

# 安装系统依赖（mysqlclient + chromadb 编译需要）
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    pkg-config \
    default-libmysqlclient-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

```dockerfile
# frontend/Dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY streamlit_app.py .

EXPOSE 8501

CMD ["streamlit", "run", "streamlit_app.py", "--server.port=8501", "--server.address=0.0.0.0"]
```

### 这段代码解决什么问题

定义镜像构建：**环境隔离 + 依赖打包 + 启动命令**。把 Python 应用变成可部署的容器。

### 关键代码逐句拆解

**① 多阶段的思想（这里是简版）**

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
```

标准流程：基础镜像 → 工作目录 → 先拷依赖清单 → 装依赖 → 拷代码 → 启动。

**细节：先 COPY requirements.txt 再 pip install，最后才 COPY . .**——利用 Docker 层缓存。改代码不重装依赖，构建飞快。

**② backend 额外装系统依赖**

```dockerfile
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*
```

Chromadb 等库需要编译工具链。`--no-install-recommends` 和 `rm -rf` 控制镜像体积。

**③ CMD — 启动命令**

```dockerfile
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- `--host 0.0.0.0`：容器内所有网络接口，**不写这个外部访问不到**。
- frontend 用 `streamlit run` 同理。

### 面试答题要点

> **Q：Dockerfile 为什么先拷 requirements 再拷代码？**
> 答：利用 Docker 构建缓存。依赖变更频率远低于代码，先把依赖层缓存住，改代码只需重新拷贝代码层，构建快得多。

> **Q：为什么 --host 0.0.0.0？**
> 答：容器内默认只监听 localhost，外部/其他容器访问不到。0.0.0.0 监听所有接口，配合 EXPOSE 和 compose 端口映射才能被访问。

---

## 8.5 ci.yml — GitHub Actions 持续集成

### 完整代码

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    services:
      mysql:
        image: mysql:8.0
        env:
          MYSQL_ROOT_PASSWORD: 123456
          MYSQL_DATABASE: code_assistant_test
        ports:
          - 3306:3306
        options: >-
          --health-cmd="mysqladmin ping -h localhost"
          --health-interval=10s
          --health-timeout=5s
          --health-retries=10
      redis:
        image: redis:7-alpine
        ports:
          - 6379:6379
        options: >-
          --health-cmd="redis-cli ping"
          --health-interval=10s
          --health-timeout=5s
          --health-retries=10

    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install dependencies
        run: |
          cd backend
          pip install fastapi uvicorn sqlalchemy aiomysql pymysql redis \
            python-jose[cryptography] bcrypt pydantic pydantic-settings python-dotenv \
            httpx pytest

      - name: Wait for services
        run: |
          python -c "
          import time, socket
          for host, port in [('127.0.0.1', 3306), ('127.0.0.1', 6379)]:
              for _ in range(30):
                  try:
                      socket.create_connection((host, port), timeout=1)
                      print(f'{host}:{port} ready')
                      break
                  except OSError:
                      time.sleep(1)
              else:
                  raise SystemExit(f'{host}:{port} not ready')
          "

      - name: Run unit tests
        run: |
          cd backend
          python -m pytest tests/test_auth.py tests/test_auth_api.py tests/test_agent_trace_api.py tests/test_eval_ragas.py tests/test_function_calling.py tests/test_fusion.py tests/test_knowledge_bases.py tests/test_rate_limit.py tests/test_user_upload.py -v
```

### 这段代码解决什么问题

**每次 push 到 main 自动跑测试**，防止坏代码进主分支。CI 里启动 MySQL/Redis 服务容器、装依赖、跑 pytest。

### 关键代码逐句拆解

**① 触发条件**

```yaml
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]
```

push 到 main、或向 main 提 PR 时触发。

**② services — 服务容器**

```yaml
services:
  mysql:
    image: mysql:8.0
    env:
      MYSQL_ROOT_PASSWORD: 123456
      MYSQL_DATABASE: code_assistant_test
    options: >-
      --health-cmd="mysqladmin ping -h localhost"
      ...
```

GitHub Actions 的 `services` 直接在测试机起 MySQL/Redis 容器（不是 Docker Compose，是 Actions 原生的 service container）。数据库名用 `code_assistant_test`，**测试数据库与开发库隔离**。

**③ Wait for services — 等端口就绪**

```python
import time, socket
for host, port in [('127.0.0.1', 3306), ('127.0.0.1', 6379)]:
    for _ in range(30):
        try:
            socket.create_connection((host, port), timeout=1)
            print(f'{host}:{port} ready')
            break
        except OSError:
            time.sleep(1)
    else:
        raise SystemExit(f'{host}:{port} not ready')
```

**30 次重试、每次 1 秒**，直到端口能连上。没等就绪就跑测试会连不上数据库导致误报失败。

**④ 跑单元测试**

```yaml
python -m pytest tests/test_auth.py tests/test_auth_api.py tests/test_agent_trace_api.py tests/test_eval_ragas.py tests/test_function_calling.py tests/test_fusion.py tests/test_knowledge_bases.py tests/test_rate_limit.py tests/test_user_upload.py -v
```

CI 现在跑 **9 个测试文件**（早期只有 3 个），覆盖：鉴权、鉴权 API、Agent 执行轨迹 API、RAGAS 评估、函数调用、RRF 融合、多知识库、限流、上传隔离。**核心思路不变——都是不加载嵌入模型/Chroma 的轻量测试**，CI 保持快速稳定。

**测试分层说明**：CI 只跑这 9 个**轻量回归**（不依赖 embedding 模型 / Chroma / 付费 Judge，能在几分钟内反馈）。本地**全量 `pytest`** 还覆盖了更重的测试——源码浏览（`test_source_api`）、客户端复用（`test_clients`）、索引生命周期（`test_code_indexer` / `test_index_lifecycle`）、检索数据集（`test_retrieval_dataset`）等。所以"CI 没跑 = 没测"是误解，重测试由本地全量回归承担。

### 面试答题要点

> **Q：CI 里为什么单独起 MySQL/Redis 服务容器？**
> 答：测试需要真实的 MySQL/Redis 才能跑集成测试（如鉴权 API 要连数据库）。GitHub Actions 的 `services` 在测试机上临时起容器，测完自动销毁，环境干净。

> **Q：CI 为什么不跑 RAG 检索相关的重型测试？**
> 答：RAG 检索测试要加载 embedding 模型（几百 MB）和 Chroma，CI 上慢且易因网络失败。所以 CI 用**轻量层**（JWT、RRF、函数调用、限流、隔离这些纯逻辑/轻依赖测试）快速反馈；RAG 的效果用本地消融实验评估。

> **Q：为什么测试数据库用 code_assistant_test？**
> 答：和开发库 code_assistant 隔离，测试产生的脏数据不污染开发环境。

---

### 第 8 层小结

组装与部署：`main.py` 把能力拼成应用，Streamlit 给人机交互，Docker Compose 一键起 4 个服务，Dockerfile 定义镜像，CI 守护代码质量。到这里，整个项目从代码到部署的完整链路就讲完了。

---

## 8.6 tests/ — 单元测试与集成测试

CI 里跑的那几个测试文件，也是项目工程化的一部分。它们验证了核心逻辑的正确性，且**刻意保持轻量**（不加载嵌入模型、不依赖 Chroma），保证 CI 快速稳定。

### 8.6.1 conftest.py — 测试环境配置

```python
"""Shared test configuration that keeps tests out of the development database."""

import os


os.environ["SKIP_SECRET_VALIDATION"] = "1"
os.environ["JWT_SECRET"] = "test-secret-only-for-ci-0123456789abcdef"
os.environ["LLM_API_KEY"] = "sk-test-only-for-ci-not-real"
os.environ["MYSQL_HOST"] = "127.0.0.1"
os.environ["MYSQL_PORT"] = "3306"
os.environ["MYSQL_USER"] = "root"
os.environ["MYSQL_PASSWORD"] = "123456"
os.environ["MYSQL_DATABASE"] = "code_assistant_test"
os.environ["REDIS_HOST"] = "127.0.0.1"
os.environ["REDIS_PORT"] = "6379"
```

**它解决什么问题**：pytest 会自动加载 conftest.py，在**任何测试执行前**设置好环境变量。作用有两个：

1. **跳过密钥校验**：`SKIP_SECRET_VALIDATION=1` 让 `config._validate_secrets()` 不拦截（测试没有真密钥）。
2. **连测试数据库**：`MYSQL_DATABASE=code_assistant_test`——**测试绝不碰开发库**，脏数据不污染开发环境。
3. **用假的 LLM 密钥**：`LLM_API_KEY=sk-test-only...` 让配置能通过校验，但测试里不会真的调 LLM。

`MYSQL_HOST=127.0.0.1` 对应 CI 里的 service 容器映射到宿主机的地址。**conftest 是"测试环境隔离"的中央开关**。

### 8.6.2 test_auth.py — 密码哈希单元测试

```python
"""密码哈希单元测试"""

import sys
import os

# 必须在 import app 之前设置：纯逻辑测试不需要真实密钥
os.environ.setdefault("SKIP_SECRET_VALIDATION", "1")
os.environ.setdefault("JWT_SECRET", "test-secret-only-for-ci-0123456789abcdef")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.auth import hash_password, verify_password


class TestPasswordHashing:
    def test_hash_then_verify_success(self):
        hashed = hash_password("mysecret")
        assert verify_password("mysecret", hashed) is True

    def test_wrong_password_fails(self):
        hashed = hash_password("mysecret")
        assert verify_password("wrong", hashed) is False

    def test_hash_is_different_each_time(self):
        h1 = hash_password("same")
        h2 = hash_password("same")
        assert h1 != h2  # bcrypt 每次加随机盐
```

**它验证什么**：bcrypt 密码哈希的核心性质——

- **正确密码能验证通过**（test_hash_then_verify_success）。
- **错误密码验证失败**（test_wrong_password_fails）。
- **相同密码两次哈希结果不同**（test_hash_is_different_each_time）——因为 bcrypt 每次加随机盐。这正是 bcrypt 比 MD5 安全的关键，用测试把它钉死。

**两个 setup 细节**：
- `sys.path.insert(0, ...)`：手动把 `backend/` 加进模块搜索路径，让 `from app.auth import ...` 能工作（pytest 从项目根跑时不一定在 sys.path 里）。
- `os.environ.setdefault(...)`：在 `import app` **之前**设置，因为 config 加载时就要读这些环境变量。**import 顺序是这类测试的经典坑**。

### 8.6.3 test_auth_api.py — 鉴权 API 集成测试

```python
"""鉴权 API 集成测试：注册 / 登录 / 刷新 / 登出 / 未授权访问

用一个只挂载 auth_router 的独立 FastAPI app 测试，避免触发 chromadb
等重型依赖加载，保证 CI 快速运行。

依赖 CI 提供的 MySQL + Redis services（见 .github/workflows/ci.yml）。
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.database import engine, Base
from app.routers.auth_router import router

# 独立 app，只挂 auth_router，不加载 chromadb 相关模块
app = FastAPI()
app.include_router(router, prefix="/api")


async def _create_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def _drop_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


async def _dispose_engine():
    await engine.dispose()


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        test_client.portal.call(_create_tables)
        yield test_client
        test_client.portal.call(_drop_tables)
        test_client.portal.call(_dispose_engine)


class TestRegister:
    def test_register_success(self, client):
        resp = client.post("/api/auth/register",
                           json={"username": "alice", "password": "secret123"})
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data

    def test_register_duplicate(self, client):
        client.post("/api/auth/register",
                    json={"username": "bob", "password": "secret123"})
        resp = client.post("/api/auth/register",
                           json={"username": "bob", "password": "secret123"})
        assert resp.status_code == 400


class TestLogin:
    def test_login_success(self, client):
        client.post("/api/auth/register",
                    json={"username": "carol", "password": "secret123"})
        resp = client.post("/api/auth/login",
                           json={"username": "carol", "password": "secret123"})
        assert resp.status_code == 200
        assert "access_token" in resp.json()

    def test_login_wrong_password(self, client):
        client.post("/api/auth/register",
                    json={"username": "dave", "password": "secret123"})
        resp = client.post("/api/auth/login",
                           json={"username": "dave", "password": "wrong"})
        assert resp.status_code == 401


class TestProtected:
    def test_no_token_returns_401(self, client):
        resp = client.post("/api/auth/logout")
        assert resp.status_code == 401

    def test_invalid_token_returns_401(self, client):
        resp = client.post("/api/auth/logout",
                           headers={"Authorization": "Bearer not-a-real-token"})
        assert resp.status_code == 401


class TestLogoutBlacklist:
    def test_logout_revokes_token(self, client):
        # 注册登录拿 token
        client.post("/api/auth/register",
                    json={"username": "erin", "password": "secret123"})
        login = client.post("/api/auth/login",
                            json={"username": "erin", "password": "secret123"})
        token = login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 登出成功
        resp = client.post("/api/auth/logout", headers=headers)
        assert resp.status_code == 200

        # token 已进黑名单，再访问受保护接口应 401
        resp = client.post("/api/auth/logout", headers=headers)
        assert resp.status_code == 401


class TestRefresh:
    def test_refresh_returns_new_tokens(self, client):
        client.post("/api/auth/register",
                    json={"username": "frank", "password": "secret123"})
        login = client.post("/api/auth/login",
                            json={"username": "frank", "password": "secret123"})
        refresh_token = login.json()["refresh_token"]

        resp = client.post("/api/auth/refresh", params={"refresh_token": refresh_token})
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data

    def test_refresh_rejects_access_token(self, client):
        client.post("/api/auth/register",
                    json={"username": "grace", "password": "secret123"})
        login = client.post("/api/auth/login",
                            json={"username": "grace", "password": "secret123"})
        access_token = login.json()["access_token"]

        # 用 access token 当 refresh token 用，应该被拒绝
        resp = client.post("/api/auth/refresh", params={"refresh_token": access_token})
        assert resp.status_code == 401
```

**它验证什么**：把 `auth_router` 挂到**独立 FastAPI app** 上，用 `TestClient`（FastAPI 自带测试客户端）跑真实 HTTP 流程。覆盖了：

- **注册**：成功返回双 token；重复用户名返回 400。
- **登录**：成功返回 token；密码错误返回 401。
- **未授权访问**：无 token / 假 token → 401。
- **登出黑名单**：登出后再用同一 token 访问 → 401（**验证 Redis 黑名单真的生效**）。
- **刷新**：refresh token 能换新 token；**用 access token 冒充 refresh token → 401**（验证 `type == "refresh"` 校验）。

**关键设计——独立 app**：

```python
app = FastAPI()
app.include_router(router, prefix="/api")
```

只挂 auth_router，**不 import 整个 main.py**。这样 `agent_router` / `search_router` 里 import 的 chromadb 等重型模块不会被加载，CI 跑得快。这是"最小化测试范围"的技巧。

**fixture 生命周期**：

```python
@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        test_client.portal.call(_create_tables)   # 测前建表
        yield test_client
        test_client.portal.call(_drop_tables)      # 测后删表
        test_client.portal.call(_dispose_engine)   # 释放连接
```

`scope="module"`：整个模块共用一次连接（不是每个测试都建删表）。建表 → 测试 → 删表 → 释放，**用完清理，不留脏数据**。

**注意**：这个测试依赖真实 MySQL + Redis（conftest 里配的 127.0.0.1）。本地跑需要先 `docker compose up mysql redis`，CI 里由 service 容器提供。

### 8.6.4 test_fusion.py — RRF 融合单元测试

```python
"""RRF 融合单元测试"""

import sys
import os

# 必须在 import app 之前设置：避免触发 config 密钥校验
os.environ.setdefault("SKIP_SECRET_VALIDATION", "1")
os.environ.setdefault("JWT_SECRET", "test-secret-only-for-ci-0123456789abcdef")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.rag.fusion import rrf


def _item(source: str, idx: int):
    return {"text": f"chunk {idx}", "source": source, "chunk_index": idx, "score": 0.0}


class TestRRF:
    def test_single_rank(self):
        results_list = [
            [_item("a.py", 0), _item("b.py", 1)],
        ]
        fused = rrf(results_list, top_n=5)
        assert len(fused) == 2
        assert fused[0]["source"] == "a.py"
        assert fused[1]["source"] == "b.py"

    def test_merge_duplicates(self):
        results_list = [
            [_item("a.py", 0)],
            [_item("a.py", 0)],
        ]
        fused = rrf(results_list, top_n=5)
        assert len(fused) == 1  # 同一个 chunk 只出现一次

    def test_rank_boost_from_both_lists(self):
        results_list = [
            [_item("a.py", 0), _item("b.py", 1)],
            [_item("b.py", 1), _item("a.py", 0)],
        ]
        fused = rrf(results_list, top_n=5)
        assert fused[0]["source"] in ("a.py", "b.py")
        assert len(fused) == 2

    def test_top_n_limit(self):
        results_list = [
            [_item(f"f{i}.py", i) for i in range(10)],
        ]
        fused = rrf(results_list, top_n=3)
        assert len(fused) == 3
```

**它验证什么**：RRF 融合算法的核心性质——纯逻辑、无依赖，是最理想的单元测试对象。

- **test_single_rank**：单路结果按原序融合。
- **test_merge_duplicates**：**同一个 chunk 在两路都出现时，只保留一条**（`(source, chunk_index)` 去重键生效）。
- **test_rank_boost_from_both_lists**：两路都召回的文档融合后排在前面。
- **test_top_n_limit**：`top_n` 截断生效。

**`_item()` 辅助函数**：构造最小测试数据（`{text, source, chunk_index, score}`），不用真实 Chroma 就能测融合逻辑——**这就是"依赖注入/接口清晰"带来的可测试性**。

### 8.6.5 test_metrics.py — 评估指标单元测试

```python
"""评估指标单元测试"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.rag.evaluation import hit_rate, mrr, ndcg


def _make_result(source: str):
    return {"text": "foo", "source": source, "chunk_index": 0, "score": 0.0}


class TestHitRate:
    def test_hit_when_expected_in_top_k(self):
        results = [_make_result("tinydb/database.py")]
        assert hit_rate(results, ["tinydb/database.py"], k=5) == 1.0

    def test_miss_when_expected_not_found(self):
        results = [_make_result("tinydb/table.py")]
        assert hit_rate(results, ["tinydb/database.py"], k=5) == 0.0

    def test_hit_any_expected(self):
        results = [_make_result("tinydb/storages.py")]
        assert hit_rate(results, ["tinydb/database.py", "tinydb/storages.py"], k=5) == 1.0

    def test_windows_backslash_normalized(self):
        results = [_make_result("tinydb\\database.py")]  # Windows 路径
        assert hit_rate(results, ["tinydb/database.py"], k=5) == 1.0


class TestMRR:
    def test_first_rank(self):
        results = [_make_result("tinydb/database.py")]
        assert mrr(results, ["tinydb/database.py"], k=5) == 1.0

    def test_second_rank(self):
        results = [
            _make_result("tinydb/table.py"),
            _make_result("tinydb/database.py"),
        ]
        assert mrr(results, ["tinydb/database.py"], k=5) == 0.5

    def test_no_match(self):
        results = [_make_result("tinydb/table.py")]
        assert mrr(results, ["tinydb/database.py"], k=5) == 0.0


class TestNDCG:
    def test_perfect_ranking(self):
        results = [
            _make_result("tinydb/database.py"),
            _make_result("tinydb/database.py"),
        ]
        assert abs(ndcg(results, ["tinydb/database.py"], k=5) - 1.0) < 0.001

    def test_relevance_at_second(self):
        results = [
            _make_result("tinydb/table.py"),
            _make_result("tinydb/database.py"),
        ]
        assert abs(ndcg(results, ["tinydb/database.py"], k=5) - 0.5) < 0.001

    def test_duplicate_source_credited_once(self):
        results = [
            _make_result("tinydb/database.py"),
            _make_result("tinydb/database.py"),
            _make_result("tinydb/database.py"),
        ]
        # 同一源文件多个 chunk，只算一次相关性，NDCG 应为 1.0（而非大于 1）
        assert abs(ndcg(results, ["tinydb/database.py"], k=5) - 1.0) < 0.001
```

**它验证什么**：三个检索评估指标的行为。有几个测试特别值得注意：

- **test_windows_backslash_normalized**：验证 `_normalize` 把 Windows 反斜杠路径转成斜杠后命中——**这个测试直接守护了"跨平台结果一致"**。
- **test_duplicate_source_credited_once**：验证 NDCG 对同一源文件的多个 chunk 只算一次相关性（`matched` 集合生效），**防止同一个文件刷分**。
- MRR 的 test_second_rank 验证"排第 2 → 0.5"的倒数排名逻辑。

### 8.6.6 test_rate_limit.py — 限流中间件测试（FakeRedis）

```python
"""Rate-limit middleware tests without a Redis server."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.middleware import RateLimitMiddleware


class FakePipeline:
    def __init__(self, store):
        self.store = store
        self.operations = []

    def zremrangebyscore(self, key, minimum, maximum):
        self.operations.append(("zremrangebyscore", key, minimum, maximum))
        return self

    def zadd(self, key, values):
        self.operations.append(("zadd", key, values))
        return self

    def zcard(self, key):
        self.operations.append(("zcard", key))
        return self

    def expire(self, key, seconds):
        self.operations.append(("expire", key, seconds))
        return self

    def execute(self):
        results = []
        for operation in self.operations:
            command, key, *args = operation
            values = self.store.setdefault(key, {})
            if command == "zremrangebyscore":
                minimum, maximum = args
                expired = [member for member, score in values.items() if minimum <= score <= maximum]
                for member in expired:
                    del values[member]
                results.append(len(expired))
            elif command == "zadd":
                values.update(args[0])
                results.append(len(args[0]))
            elif command == "zcard":
                results.append(len(values))
            else:
                results.append(True)
        return results


class FakeRedis:
    def __init__(self):
        self.store = {}

    def pipeline(self):
        return FakePipeline(self.store)


def test_second_api_request_is_rate_limited():
    app = FastAPI()
    app.add_middleware(
        RateLimitMiddleware,
        rate_limit=1,
        window_seconds=60,
        redis_client=FakeRedis(),
    )

    @app.get("/api/ping")
    async def ping():
        return {"ok": True}

    with TestClient(app) as client:
        assert client.get("/api/ping").status_code == 200
        assert client.get("/api/ping").status_code == 429
```

**它验证什么**：限流中间件的核心行为——**第二个请求被限**。用 `rate_limit=1`，第一个请求 200，第二个请求 429。

**关键设计——FakeRedis / FakePipeline**：不用真实 Redis，而是**手写一个内存版 ZSET 实现**，模拟 `zremrangebyscore` / `zadd` / `zcard` / `expire` 的行为。这样限流测试**完全不需要 Redis 服务**，CI 上稳定快速。这依赖 `middleware.py` 的 `redis_client` 注入参数——**为了可测试性，中间件允许外部传入 redis_client**（这是 middleware 改动的原因之一）。

### 8.6.7 test_user_upload.py — 上传隔离单元测试（FakeRetriever）

```python
"""Upload-index unit tests that avoid loading the embedding model."""

import importlib
import sys
import types


def test_upload_index_uses_private_collection_and_owner_filter(monkeypatch):
    class FakeChunker:
        def chunk(self, documents):
            return [{
                "text": documents[0]["content"],
                "metadata": {"source": documents[0]["path"], "chunk_index": 0},
            }]

    class FakeRetriever:
        instances = []

        def __init__(self, collection_name):
            self.collection_name = collection_name
            self.added_chunks = []
            self.search_args = None
            self.__class__.instances.append(self)

        def add_chunks(self, chunks):
            self.added_chunks = chunks
            return ["chunk-id"]

        def search(self, query, k, where):
            self.search_args = (query, k, where)
            return [
                {"text": "own", "source": "upload/own.py", "owner_id": 7},
                {"text": "other", "source": "upload/other.py", "owner_id": 8},
            ]

    fake_chunker = types.ModuleType("app.rag.chunker")
    fake_chunker.CodeChunker = FakeChunker
    fake_dense = types.ModuleType("app.rag.dense_retriever")
    fake_dense.DenseRetriever = FakeRetriever
    fake_dense.USER_CORPUS = {"source_type": "user_upload"}
    fake_dense.USER_UPLOAD_COLLECTION = "user_uploads"

    monkeypatch.setitem(sys.modules, "app.rag.chunker", fake_chunker)
    monkeypatch.setitem(sys.modules, "app.rag.dense_retriever", fake_dense)
    monkeypatch.delitem(sys.modules, "app.rag.user_upload", raising=False)
    module = importlib.import_module("app.rag.user_upload")

    index = module.UserUploadIndex()
    assert index.retriever.collection_name == "user_uploads"

    assert index.add_file("own.py", "private code", owner_id=7) == 1
    metadata = index.retriever.added_chunks[0]["metadata"]
    assert metadata["source_type"] == "user_upload"
    assert metadata["owner_id"] == 7

    assert index.search("private", owner_id=7) == [
        {"text": "own", "source": "upload/own.py", "owner_id": 7}
    ]
    assert index.retriever.search_args == (
        "private", 5, {"source_type": "user_upload", "owner_id": 7}
    )
```

**它验证什么**：上传索引的**两个关键隔离行为**：
1. **`UserUploadIndex` 用的是 `user_uploads` 独立 collection**（`index.retriever.collection_name == "user_uploads"`）。
2. **检索时 owner 过滤生效**：`search` 传的 `where` 是 `{"source_type": "user_upload", "owner_id": 7}`，且返回结果只包含自己的（fake 返回了 owner 7 和 owner 8 两条，但结果只剩 owner 7 的）——**应用层兜底过滤生效**。

**关键设计——monkeypatch 模块替换**：用 `types.ModuleType` 造假的 `app.rag.chunker` / `app.rag.dense_retriever` 模块塞进 `sys.modules`，再 `import_module("app.rag.user_upload")`。**这样不加载真实的 embedding 模型 / Chroma，纯测隔离逻辑**。

### 8.6.8 test_function_calling.py — Agent 工具调用测试（无 LLM）

```python
"""Function-calling harness tests without a live LLM or database."""

from pydantic import BaseModel, Field

from app.agent import llm
from app.agent.harness import AgentHarness
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

    def fake_call(messages, tools):
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

    def fake_call(messages, tools):
        requests.append(messages.copy())
        return next(responses)

    monkeypatch.setattr("app.agent.harness.call_llm_with_tools", fake_call)

    assert harness.run("look up") == "invalid arguments"
    assert tool.calls == []
    assert harness.execution_trace[0]["status"] == "rejected"
    assert harness.execution_trace[0]["arguments"] is None
    assert '"error"' in requests[1][-1]["content"]


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
        lambda messages, tools: next(responses),
    )

    assert harness.run("look up TinyDB") == "final answer"
    assert tool.calls == [{"query": "TinyDB"}]
    assert [item["status"] for item in harness.execution_trace] == ["completed", "rejected"]
    assert "Repeated tool call" in harness.execution_trace[1]["observation"]
```

**它验证什么**：Agent 工具调用循环的三个核心行为——**完全不依赖真实 LLM 和数据库**（monkeypatch 掉 `call_llm_with_tools`，用一个假工具 `LookupTool`）：

1. **有效工具调用执行**：合法的 `tool_calls` → 参数被 Pydantic 校验 → 工具执行 → tool 消息注入 → 返回最终答案。
2. **非法参数被拒**：`{"query": ""}` 违反 `min_length=1` → `ValidationError` → 状态 `rejected`，**工具没执行**（`tool.calls == []`），错误作为 observation 返回。
3. **重复工具调用被拒**：同一个 `(name, arguments)` 调用两次 → 第二次状态 `rejected`，observation 含 "Repeated tool call"——**验证了防死循环机制**。

**为什么这个测试很值钱**：它把 Agent 循环的关键逻辑（校验、状态分类、防重复、轨迹）全部钉死，且零外部依赖，CI 秒跑。

### 8.6.9 其他测试文件（test_agent_trace_api / test_eval_ragas / test_knowledge_bases）

CI 还跑另外三个测试文件（内容随项目演进，这里给职责说明）：

- **`test_agent_trace_api.py`**：鉴权 API + Agent 执行轨迹接口的集成测试——验证 `/api/agent/chat` 返回的 `trace` 结构符合预期。
- **`test_eval_ragas.py`**：RAGAS 脚本**离线契约测试**——不安装 RAGAS、不调用 Judge、不计算指标，只验证 `build_samples` 的样本结构、题集加载（tinydb/project 题数）和 `_judge_base_url` 的端点格式校验。
- **`test_knowledge_bases.py`**：多知识库定义测试——验证 `KNOWLEDGE_BASES` 的注册、`get_knowledge_base` 的查找、未知 ID 抛异常。

> 注：这三个文件我没有逐一展开代码，因为它们属于"随项目演进的辅助测试"。你可以打开源码结合本节理解——它们的核心都是"用轻量依赖验证某块逻辑"。

### tests/ 小结

`tests/` 目录体现了两个工程原则：

1. **测试分层**：纯逻辑测试（test_fusion、test_metrics、test_auth 的哈希）快而稳定；集成测试（test_auth_api）依赖 MySQL/Redis 但覆盖真实 HTTP 流程。CI 跑轻量层，保证快速反馈。
2. **环境隔离**：conftest.py 把测试导向 `code_assistant_test` 库、跳过密钥校验、用假 LLM 密钥——测试环境绝不污染开发环境。

---

# 第 9 章 全链路数据流总结

把前面 8 层的所有文件串起来，看**一次真实交互**的完整数据流。

## 9.1 全链路流程图

```
用户（Streamlit 前端）
  │  输入问题（选择知识库 tinydb / project）
  ▼
POST /api/agent/chat  ──► middleware.py 限流检查（Redis ZSET 滑动窗口）
  │                     ──► auth.py get_current_user（JWT 验签 + Redis 黑名单 + 查库）
  ▼
agent_router.chat
  │  ① scoped_session_id = f"{knowledge_base}:{session_id}"
  │  ② get_or_create_conversation（conversation_service → MySQL）
  │  ③ load_history（conversation_service → MySQL → 最近20条）
  │  ④ harness.run（asyncio.to_thread → 线程池）
  ▼
AgentHarness.run（tool-calling 循环，最多 AGENT_MAX_STEPS=4 步）
  │  组装 messages：build_system_prompt(knowledge_base) + 历史 + 用户问题
  │  + get_tool_schemas()（各工具的 function_schema）
  ▼
call_llm_with_tools（llm.py → DeepSeek API，tools 参数，重试+退避）
  │
  ▼ 循环判断
  ├─ 有 tool_calls
  │     │  逐个：validate_args（Pydantic 校验）
  │     │       → 指纹去重（executed_actions）
  │     │       → execute_tool（tools.py）
  │     │          ├─ SearchCode → DenseRetriever + SparseRetriever + RRF
  │     │          ├─ ExplainCode → 检索 + LLM 解释
  │     │          └─ GenerateTest → 检索 + LLM 写测试
  │     │      状态分类（completed / rejected / failed）→ execution_trace
  │     │      tool 消息注入 messages → 继续循环
  │     └─ _schedule_log → agent_logs 表
  │
  └─ 无 tool_calls = 最终答案（content）
        ▼
conversation_history 更新 → 返回 answer + trace + citations + metrics
  ▼
save_message（user + assistant → messages 表）
  ▼
ChatResponse（answer + trace + citations + metrics）返回给前端
  → 前端展示执行轨迹、引用代码、性能指标
```

## 9.2 三种典型交互

**① 登录（首次使用）**

```
前端 POST /api/auth/register ──► 查重（users 表）
                               ──► bcrypt 哈希密码
                               ──► 建用户 → 签发 access + refresh token
前端存 token → 按知识库生成独立 session_id → 进入对话页
```

涉及：`auth_router.register` → `auth.hash_password` / `create_access_token` → `models/user.py`。

**② Agent 对话（核心场景）**

```
用户（选 tinydb）：TinyDB 怎么存数据？
Agent 第1步：call_llm_with_tools → 返回 tool_calls [{"name":"search","arguments":{...}}]
  → validate_args（Pydantic 校验）→ 执行 SearchCode → Chroma + BM25 + RRF → top5 代码片段
  → tool 消息注入 → 继续
Agent 第2步：LLM 基于检索到的 storages.py 代码，组织中文回答
  → 无 tool_calls → 取 content 为答案
→ 保存 user/assistant 消息 → 返回 answer + trace → 前端展示执行轨迹
```

涉及：`agent_router.chat` → `harness.run` → `llm.call_llm_with_tools` → `tools.SearchCode` → `dense_retriever` / `sparse_retriever` / `fusion.rrf` → `agent_logs` / `conversation_service`。

**③ 检索（不走 Agent）**

```
前端 POST /api/search {query, knowledge_base, use_hybrid: true}
  → 按知识库建 DenseRetriever / SparseRetriever
  → rewrite（如果 use_hyde）→ query_rewrites 表
  → async_hybrid_search → dense + sparse → RRF → retrieval_logs 表
  → 返回 top-k 代码片段 + 真实 latency_ms
```

涉及：`search_router.search` → `fusion.async_hybrid_search` → `query_rewriter` → `retrieval_logs`。

## 9.3 数据在哪些表里流转

| 环节 | 写哪张表 | 谁写的 |
|------|---------|--------|
| 注册/登录 | `users` | auth_router |
| 会话创建 | `conversations` | conversation_service |
| 对话消息 | `messages` | conversation_service |
| Agent 每步决策 | `agent_logs` | harness._schedule_log |
| 每次检索链路 | `retrieval_logs` | fusion.async_hybrid_search |
| 查询改写 | `query_rewrites` | query_rewriter |
| 消融实验 | `evaluation_runs` | evaluation.run_ablation |
| 索引重建 | `index_versions` | code_indexer |
| 点赞/点踩 | `feedbacks` | 预留（前端未接入） |

## 9.4 可观测性：出了问题怎么看

项目有几层可观测：

- **日志**（logger.py）：代码里的 `log.info/warning/error`，带模块名和函数名。
- **检索黑匣子**（retrieval_logs）：一次检索的稠密路、稀疏路、融合结果、延迟全记录。
- **Agent 黑匣子**（agent_logs）：Agent 每步的工具调用摘要（工具名、参数、状态、观察）。
- **执行轨迹**（execution_trace）：内存中的结构化轨迹，**返回给前端展示**——用户能看到 Agent 每一步做了什么（状态 completed/rejected/failed）。

**面试可以讲**：如果某个用户反馈"Agent 答得不对"，我可以查 `agent_logs` 回放它每步做了什么——第 2 步调了 search 传了什么参数、状态是 completed 还是 rejected、Observation 是什么。同时前端能看到 execution_trace，用户自己也能发现"某一步参数被拒了"。这种"可回放的决策链路"是 Agent 应用生产化的关键。

---

# 第 10 章 潜在改进建议

以下改进点按"性价比"排序。前几个是"低成本高收益"，最后一个可以做成"你主动说出的架构演进"。

## 10.1 DenseRetriever 的 embedding 模型缓存（已完成）

**现状**：`dense_retriever.py` 已通过 `get_embeddings()` + `_embedding_models` 字典实现了**进程级 embedding 模型缓存**（每个 (模型, 设备) 组合只加载一次），并用 `_chroma_clients` 复用了 Chroma 持久化客户端。**这个改进已经落地**，不再是待办。

**真实遗留**：
- 检索器实例本身每次请求仍会 `DenseRetriever(collection_name=...)` 新建（但模型和 Chroma client 是复用的，所以开销已大幅降低）。
- 若想更进一步，可把 `DenseRetriever` 实例也做成按 collection 复用的单例（注意 Chroma 的线程安全性，需要加锁）。

**面试可以讲**："我意识到 embedding 模型加载是主要开销，用进程级缓存 + 线程锁让每个模型只加载一次，检索器实例轻量化复用底层客户端。"

## 10.2 Agent 流式输出的进一步优化（已实现基础版）

**现状**：SSE 流式对话已实现（`/agent/chat/stream`），支持 status / delta / trace / done / error / cancelled 事件，前端有打字机效果。

**可改进**：目前流式只覆盖**最终回答**（工具调用阶段仍是 status 提示）。可以进一步：
- 把工具调用的**参数校验过程**也流式化（tool_call 中间态）。
- 加 **中断按钮**（前端发取消请求，而不是只靠断开连接）。
- 考虑 WebSocket 双向通道（SSE 是单向的，取消需要额外请求）。

**价值**：体验从"打字机"升级为"完全实时可交互"。

## 10.3 检索接口的延迟统计粒度

**现状**：`/api/search` 的 `latency_ms` 已修复为真实端到端耗时（`time.perf_counter()`）。

**改法**：可以进一步细化——把延迟拆成"改写耗时 / 检索耗时 / 重排耗时"三段，分别打点，方便定位瓶颈。

**价值**：接口完整性的进阶——不仅知道总耗时，还能看出哪一段拖慢了。

## 10.4 Redis 客户端统一管理（已完成）

**现状**：`clients.py` 已提供**进程级共享 Redis 客户端**（`get_redis_client()` 惰性单例 + 线程锁 + 短超时 + 不重试），auth 黑名单、限流、稀疏检索、重排都统一走它。**连接创建逻辑的重复已经消除**，不再是待办。

**真实遗留**：
- 各模块对"Redis 返回 None 时如何降级"仍各自处理（黑名单跳过、限流禁用、缓存不生效），行为基本一致但未抽成统一策略。
- 可以进一步封装一个统一的"降级包装器"，让所有调用方用同一套降级约定。

**面试可以讲**："我把分散在各模块的 Redis 连接抽成了 `clients.py` 的进程级单例，统一短超时与不重试策略，Redis 挂了各模块自动降级。"

## 10.5 为 feedbacks 表接入前端

**现状**：`feedbacks` 表存在，但前端没有点赞/点踩按钮，路由也没有对应接口。

**改法**：加 `/api/feedback` 接口 + 前端按钮，收集用户对回答的反馈，为后续微调/评测提供真实数据。

**价值**：闭环数据飞轮——真实反馈是评估的"金标准"。

## 10.6 向量化检索与关键词检索的并发（成本中、收益中）

**现状**：`hybrid_search` 串行执行 dense 和 sparse。

**改法**：`dense.search` 和 `sparse.search` 并行（`asyncio.gather` + `to_thread`），两路无依赖，可以同时跑。

**价值**：延迟减半（两路中最慢的那个），体现对并发的理解。

## 10.7 索引生命周期管理（部分完成）

**现状**：`code_indexer.py` 已有**受控重建**——`_rebuild_lock` 防并发、返回 `busy / skipped / ready / failed` 状态、空源码时保留旧索引、collection 替换失败时回滚旧内容。**这已经是一个相当完整的索引生命周期**，不再是待办。

**真实遗留**：
- 仍未实现"**源码变更自动触发重建**"——目前重建靠手动执行 `python -m app.rag.code_indexer`。
- **Chroma 与 Redis 不是原子切换**：重建顺序是"先替换 Chroma（`replace_chunks`）→ 再写 Redis BM25（`from_chunks` → `_save_to_redis`）"。若 Redis 写入失败（`_save_to_redis` 里 `except` 吞掉异常），会出现**"新 Dense + 旧/空 BM25"** 的短暂不一致。`_rebuild_lock` 和 Dense 回滚只降低了部分重建失败的风险，并不能保证两路原子一致。

**面试可以讲**："我用锁 + 状态机（busy/skipped/ready/failed）+ 空源保留旧索引 + Dense 替换失败回滚来管理索引生命周期，减少了并发重建和半更新的风险。但要诚实说明：Chroma 与 Redis 的切换不是原子事务，Redis 写失败时可能出现新 Dense + 旧 BM25 的不一致——彻底解决需要版本化 collection 和显式切换流程。"

## 10.8 单元测试覆盖扩展

**现状**：CI 已经跑了 9 个测试文件（鉴权、鉴权 API、Agent 轨迹 API、RAGAS、函数调用、RRF、知识库、限流、上传隔离）。但仍有一些模块没有测试。

**改法**：为 `conversation_service`（会话持久化）、`query_rewriter`（HyDE 改写记录落库）、`fusion.async_hybrid_search`（检索日志落库）补测试；`test_eval_ragas` 如果依赖真实模型，可考虑 mock。

**价值**：测试覆盖是工程质量的门面。README 里写的安全修复（隔离、限流）最好都有测试背书——现在已经有了（test_rate_limit / test_user_upload），可以继续扩大。

---

# 附录 A 环境变量参考

| 变量 | 必填 | 默认值 | 说明 |
|------|------|--------|------|
| `LLM_API_KEY` | ✅ | - | DeepSeek API 密钥（sk- 开头） |
| `LLM_API_ENDPOINT` | 否 | DeepSeek | LLM 服务地址（Ollama 本地可切换） |
| `LLM_MODEL` | 否 | deepseek-v4-flash | 模型名 |
| `JWT_SECRET` | ✅ | - | JWT 签名密钥，至少 32 字符 |
| `MYSQL_HOST` | 否 | localhost | MySQL 地址 |
| `MYSQL_PORT` | 否 | 3306 | MySQL 端口 |
| `MYSQL_USER` | 否 | root | MySQL 用户 |
| `MYSQL_PASSWORD` | 否 | 123456 | MySQL 密码 |
| `MYSQL_DATABASE` | 否 | code_assistant | 数据库名 |
| `REDIS_HOST` | 否 | localhost | Redis 地址 |
| `REDIS_PORT` | 否 | 6379 | Redis 端口 |
| `REDIS_CACHE_TTL` | 否 | 300 | 检索缓存过期（秒） |
| `CHROMA_PERSIST_DIR` | 否 | ./data/chroma | Chroma 持久化目录 |
| `REPO_PATH` | 否 | ./data/target_repo | tinydb 知识库源码路径 |
| `PROJECT_SOURCE_PATH` | 否 | . | project 知识库源码路径（项目自身） |
| `EMBEDDING_MODEL` | 否 | sentence-transformers/all-MiniLM-L6-v2 | embedding 模型（中文场景可换 BAAI/bge-small-zh-v1.5） |
| `EMBEDDING_DEVICE` | 否 | cpu | embedding 推理设备 |
| `CHUNK_STRATEGY` | 否 | recursive | 分块策略（recursive / semantic / token） |
| `CHUNK_SIZE` / `CHUNK_OVERLAP` | 否 | 500 / 50 | 分块大小与重叠 |
| `AGENT_MAX_STEPS` | 否 | 4 | Agent 最大工具调用轮数 |
| `AGENT_MAX_DURATION_SECONDS` | 否 | 75.0 | Agent 总时长预算（秒） |
| `AGENT_LLM_TIMEOUT_SECONDS` | 否 | 15.0 | 协调 LLM 单次调用超时 |
| `AGENT_REQUEST_TIMEOUT_SECONDS` | 否 | 80.0 | 整个 Agent 请求超时 |
| `RAGAS_JUDGE_ENDPOINT` / `MODEL` / `API_KEY` | 否 | 同 LLM_* | RAGAS 评估时的 Judge LLM 配置（默认复用业务 LLM） |

> 密钥生成命令：`python -c "import secrets; print(secrets.token_hex(32))"`

---

*文档完。按「地基 → 数据 → 安全 → RAG → Agent → 服务 → 路由 → 部署 → 测试」的顺序，覆盖了项目的核心实现、部署配置与主要测试文件。祝你面试顺利！*