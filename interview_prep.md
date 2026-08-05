# Code Assistant Agent — 面试准备手册

> 适用方向：AI 大模型应用开发 / Agent 方向实习（非算法岗）
> 范围：项目拷打 + RAG + Agent + LLM 基础 + Python + Redis + MySQL + LangChain/LangGraph

---

## 第一部分：项目拷打（模拟面试 Q&A）

### 一、项目总览

**Q: 介绍一下你这个项目。**

A: 这是一个智能代码助手 Agent。用户可以用自然语言问关于代码库（TinyDB 开源项目）的问题，Agent 通过 ReAct 循环自主决定调用哪个工具（搜索代码、解释函数、生成测试），最终给出答案。整个过程有对话记录，支持多轮上下文。数据模型里预留了反馈表（点赞/点踩），作为后续优化方向的候选。

技术上它分成四层：
- **RAG 层**：多策略分块器把源码切成代码块，做混合检索（Dense + Sparse）+ RRF 融合 + HyDE 查询改写 + cross-encoder 重排，配了完整的消融实验评估
- **Agent 层**：自研了一个轻量 Harness，管理 ReAct 循环和工具注册，决策链路完整存入 MySQL，多轮对话历史持久化到数据库
- **API 层**：FastAPI 异步框架，JWT 鉴权 + Redis 黑名单登出，Redis 滑动窗口限流，文件上传索引
- **部署层**：Docker Compose 一键启动（MySQL + Redis + 后端 + 前端），GitHub Actions 做 CI

**面试官追问：你遇到最大的技术挑战是什么？**

> 准备答案示例（任选一个真实经历）：
>
> **① LLM 输出格式不稳定导致 Agent 循环跑飞。** 一开始我用正则 `\{[^{}]*"name"...\}` 从 LLM 输出里提取 Action JSON，但 `args` 里也有花括号，正则匹配不上，Agent 就一直空转直到 max_steps。后来我改成一个花括号深度扫描的解析器（`_extract_json_action`），能正确处理嵌套 JSON。这让我意识到：**Agent 的可靠性瓶颈往往不在 LLM 智商，而在输出解析的鲁棒性**。
>
> **② 评估全 0 分，排查发现是 Windows 路径分隔符。** 消融实验第一次跑出来 Hit Rate 全是 0，我一度以为是检索坏了。后来打印诊断才发现：Windows 上 `os.path.relpath` 返回 `tinydb\database.py`（反斜杠），而测试集里写的是 `tinydb/database.py`（正斜杠），字符串匹配永远失败。修法是在指标函数里统一 `replace("\\", "/")`。这个坑说明：**评估代码的细节（路径、编码）往往比算法本身更容易出错**。

---

### 二、RAG 相关

**Q: 为什么选 all-MiniLM-L6-v2 而不是 OpenAI 的 embedding？**

A: 两个原因。第一，本地模型不需要网络调用和 API Key，开发迭代快，面试演示时也不依赖网络。第二，对于代码检索场景，384 维的向量已经够用，它速度快、体积小（约 80MB）。如果生产环境需要更高精度，config.py 里一行切换模型名。

**Q: 三种分块策略你怎么选的？给我讲讲对比结果。**

A: 我做了对比实验：Recursive 策略优先在空行和 def/class 边界切分，保持了每块的语义完整性，适合代码；Semantic 策略按函数/类边界切，块更大但数量少；Token 策略按 token 数切，最均匀但可能切断函数逻辑。最终选 Recursive 作为默认。chunk_size 500、overlap 50，让边界信息至少在一个 chunk 里完整。设计成策略模式，config.py 一行切换。

**Q: 混合检索是怎么做的？**

A: 同时跑两条路——Dense 路用 all-MiniLM 把 query 转成 384 维向量在 Chroma 里做相似度搜索；Sparse 路用 rank_bm25 库做关键词匹配。两路各自返回 top-10 后，用 RRF（Reciprocal Rank Fusion）融合排序。公式是 1/(k + rank)，k 取 60。好处是不需要调权重、对分数尺度不敏感。

**Q: 消融实验的数据是什么？**

A: 我构建了 20 条中文测试 query，每条标注了期望命中的源文件，用 Hit Rate / MRR / NDCG 三个指标评估。真实跑出来的结果（security 加固、索引重建后的最新一轮）：

| 配置 | Hit Rate | MRR | NDCG | 延迟(ms) |
|------|----------|-----|------|----------|
| dense only | 0.95 | 0.60 | 0.60 | 13 |
| sparse only | 0.95 | 0.60 | 0.60 | 0.3 |
| hybrid (RRF) | 0.95 | 0.60 | 0.60 | 0.4 |
| hybrid + HyDE | 0.95 | 0.60 | 0.60 | 3620 |
| hybrid + HyDE + rerank | 0.85 | 0.49 | 0.48 | 3900 |

（注：具体数字以你本地最后一次 run_eval 结果为准，面试前重跑一遍确认）

结论有两个：
1. **基础检索已经很强**：Hit Rate 达到 0.95，dense / sparse / hybrid 三项完全持平——说明在这个测试集上，双路召回的结果高度重合，RRF 融合和 HyDE 都没有带来增量（反而 HyDE 的延迟涨到 3.6 秒）。这是一个诚实的观察：混合检索的价值在代码场景主要体现在对特定查询（缩写、术语）的互补，在通用问题上不一定有提升。
2. **reranker 在我们场景降了**：cross-encoder/ms-marco-MiniLM-L-6-v2 是在网页搜索（MS MARCO）上训练的，对代码检索不敏感，把正确结果排后面去了，Hit Rate 从 0.95 掉到 0.85。这是一个有价值的负面结论——说明 reranker 不是加了就一定好，要看领域匹配。

**Q: RRF 和加权融合有什么区别？为什么选 RRF？**

A: RRF 不需要调权重，公式决定了两个路的结果会自动平衡。加权融合需要人为设定 dense 占 0.7 还是 0.6，这个值不同场景下最优解不一样，调起来很麻烦。RRF 用 rank 位置而不是分数做融合，天然不敏感分数尺度——dense 返回的分数是 0 到 1 之间的，BM25 的分数可以到几十，加权融合根本不好加。RRF 就没有这个问题。

**Q: cross-encoder 和 bi-encoder 有什么区别？**

A: Bi-encoder 是 query 和 document 各自独立编码成向量，然后算相似度。速度快，可以离线建索引，适合召回阶段。Cross-encoder 是把 query 和 document 拼在一起送进模型做一次前向传播，精度更高但慢很多，适合精排阶段。我的流程是：bi-encoder 从 215 个块里召回 top-10，cross-encoder 对这 10 个重新打分取 top-3。

**Q: HyDE 查询改写是什么原理？**

A: HyDE（Hypothetical Document Embedding）的思路是：用户问题往往很短（比如"insert 方法怎么工作"），直接做 embedding 效果不好。先让 LLM 根据问题"猜"一段理想的代码长什么样，然后用这段假代码去做 embedding 检索。假代码比原始问题更接近代码库的分布，所以检索效果更好。本质上是在做 query → document 的模态对齐。

---

### 三、Agent 相关

**Q: 你的 Agent 循环是怎么实现的？**

A: 标准 ReAct 模式：
```
while True:
    ① 把系统提示词（含工具描述）+ 对话历史 + 用户问题 拼成 messages 送 LLM
    ② LLM 输出 Thought（思考）和 Action（要调用的工具 + JSON 参数）
    ③ 用花括号深度扫描解析 Action JSON，执行工具，返回 Observation
    ④ Observation 追加到上下文
    ⑤ LLM 判断是否已经够信息给出最终答案
    ⑥ 如果够了，输出最终答案；否则回到①
```
每一步的决策链（thought / action / observation）都存到 MySQL 的 agent_logs 表里。循环有 max_steps=6 兜底，防止死循环。

**Q: Harness 是做什么的？为什么不用 LangGraph？**

A: Harness 是 Agent 的轻量运行框架——它负责三件事：工具注册（把 Tool 子类实例注册进 tool_map）、执行轨迹记录（agent_logs 落库）、多轮对话历史恢复。LangGraph 功能更强但封装太厚，面试时面试官一问"图状态怎么传递"就容易卡壳。我自己写的 Harness 每个方法都能讲清楚设计意图。而且架构上预留了扩展位，以后想换可以换。

**Q: 三个工具是怎么注册到 Agent 的？**

A: 我定义了一个抽象基类 `Tool`，声明了 name、description、parameters 属性和抽象的 execute 方法。每个具体工具（SearchCode / ExplainCode / GenerateTest）继承它并实现 execute。Harness 维护一个 `AVAILABLE_TOOLS` 列表和 `tool_map` 字典，把工具描述注入 LLM 的 system prompt，LLM 根据描述决定调哪个。新增工具只需要写一个继承 Tool 的类，加进列表，零侵入。

**Q: 多轮对话是怎么实现的？**

A: 分两层。运行时：harness 内部维护 `conversation_history`，每轮把 user/assistant 消息追加进去，下一轮拼进 messages 一起送 LLM。持久化：agent_router 每次请求先调 `get_or_create_conversation` 拿会话，再从 MySQL 的 messages 表 `load_history` 恢复历史注入 harness，Agent 跑完后把本轮消息 `save_message` 存库。这样跨请求、跨服务重启都能恢复上下文。

**Q: Agent 怎么评估的？**

A: 我构建了 8 个覆盖 TinyDB 核心模块的测试任务（存储、查询、并发、中间件等），每个任务有"问题 + 参考答案要点"。跑完每个任务后，用 all-MiniLM 把 Agent 的回答和参考答案各转成向量，算余弦相似度作为得分，全部自动化、可复现。平均相似度 0.60，其中存储机制 0.71 最高、数据操作 0.47 最低——说明纯检索不足以支撑需要代码逻辑推理的问题。

**Q: 你试过哪些 Agent 评估方案？为什么选语义相似度？**

A: 试过三种。一开始用关键词匹配（检查回答是否包含预定关键词），发现太死板，同义词和语序变化全判错。然后试过 LLM 当裁判打分，但裁判没看过源码、没有标准答案，分数是瞎给的，而且有成本有随机性。最后用 embedding 余弦相似度——确定性强、零成本、可扩展到大测试集。三种方案的权衡本身就是面试可讲的内容。

**Q: 用户反馈数据怎么用的？**

A: 目前 Feedback 表建好了（存 message_id、rating 1/-1、可选评论文本），但**还没接 API 和前端**，是规划中的能力。我的设想是：前端每条回答加点赞/点踩，存进 Feedback 表，用来算点赞率作为 Agent 质量的粗略指标；点踩的数据可以拉出来分析哪些类型的问题 Agent 容易答错，针对性地优化 prompt。这是下一步计划，不是已上线功能——面试时我会如实说明状态。

---

### 四、架构与工程相关

**Q: 你为什么用 FastAPI 不是 Flask？**

A: FastAPI 原生支持异步，对于我这个项目来说很重要——Agent 循环可能涉及多次 LLM 调用，如果用 Flask 同步框架，每个请求都会阻塞住整个 worker 线程，并发能力差。FastAPI 基于 Starlette + Pydantic，自动生成 OpenAPI 文档（/docs 可直接调试接口），类型检查也更严格。

**Q: 异步 SQLAlchemy 和同步有什么区别？**

A: 核心区别在于数据库 I/O 是否阻塞事件循环。同步 SQLAlchemy 执行查询时，线程挂起等待数据库返回结果。异步 SQLAlchemy（通过 aiomysql 驱动）在等待数据库时让出事件循环，服务器可以处理其他请求，用更少的资源支持更多并发。注意异步代码里不能直接 time.sleep()，要用 asyncio.sleep()，否则会阻塞整个事件循环。

**Q: 你们踩过一个 asyncio 的坑？**

A: 有。Agent 的决策日志是异步写的，在脚本里直接 `asyncio.create_task()` 没问题。但走 FastAPI 接口时，`harness.run()` 被 `asyncio.to_thread()` 丢到后台线程跑，线程里没有运行中的事件循环，`create_task` 直接抛 `RuntimeError: no running event loop`。修法是加一个 `_schedule_log` 辅助函数：检测当前有没有运行中的事件循环，有就 `create_task`，没有就 `asyncio.run` 独立跑。这让我理解了**线程和事件循环的关系**。

**Q: JWT 的黑名单是怎么实现的？**

A: JWT 的天然缺陷是一旦签发，在过期之前无法撤回。我用 Redis 做了一层黑名单：用户调用登出接口时，把整个 access_token 字符串作为 key 存入 Redis（`blacklist:{token}`），TTL 设为 token 的剩余有效期。验证中间件（get_current_user）里先检查这个 token 是否在 Redis 黑名单中，在就直接 401。这样既能让 token 即时失效，又不会长期占用 Redis 内存。

**Q: 你为什么不自己做登录 session 用 Cookie 而要选 JWT？**

A: 两个原因。第一，JWT 是无状态的，服务端不需要存 session，方便水平扩展——部署多个副本时不需要共享 session 存储。第二，我这个项目既有后端 API 又有 Streamlit 前端，JWT 可以方便地在不同客户端之间传递（API 请求头 Bearer token），而 Cookie 受同源策略限制。

**Q: 你做了哪些并发方面的考虑？**

A: 两点落地：第一，Redis 滑动窗口限流中间件，用 ZSET 实现真正的滑动窗口——每个请求时间戳作为一个 member，删除窗口外的旧记录后统计窗口内数量，对每个用户（从 JWT 解析）每分钟限 60 次请求，防止打满 DeepSeek API 的频率限制。Redis 挂了自动降级跳过限流，不影响可用性。第二，Agent 的同步检索调用用 `asyncio.to_thread` 扔到线程池，不阻塞 FastAPI 事件循环。

**Q: LLM 调用层是怎么封装的？**

A: `llm.py` 里封装了 `call_llm` 和 `call_llm_with_messages`。关键设计：① 通过 config 切换 DeepSeek / Ollama，请求头自动带 Bearer token；② 兼容两种响应格式（Ollama 的 `message.content` 和 OpenAI/DeepSeek 的 `choices[0].message.content`）；③ 重试 + 指数退避（失败后等 1s、2s 再试），最多 3 次；④ 重试全部失败返回空串，由调用方兜底。

---

## 第二部分：RAG 八股文

### 基础概念

**Q: RAG 解决的是什么问题？**

A: 大模型的训练数据有截止日期，而且不包含私有数据。RAG（Retrieval-Augmented Generation）通过从外部知识库检索相关信息，注入到 LLM 的上下文中，让 LLM 能基于最新、最相关的信息回答。优点是不需要重新训练模型，成本低、可解释性强、知识可更新。

**Q: RAG 的完整链路是什么样的？**

A:

```
文档 → 切分 → embedding → 存入向量库
                    ↓
用户 query → query 改写 → embedding → 检索（dense + sparse）
                    ↓
               RRF 融合 → re-rank → 注入 prompt → LLM 生成
```

**Q: Dense Retrieval 和 Sparse Retrieval 各有什么优缺点？**

| | Dense | Sparse |
|---|---|---|
| 原理 | 语义匹配 | 关键词匹配 |
| 优点 | 理解同义词、近义词 | 精确匹配、不需要训练 |
| 缺点 | 稀有词效果差、需要训练 | 无法处理语义相似但关键词不同的情况 |
| 典型实现 | Chroma + all-MiniLM | BM25 |

**Q: Chunk 大小怎么定？**

A: 取决于 embedding 模型的输入长度上限。all-MiniLM-L6-v2 是 256 tokens（约 200-300 英文单词）。chunk_size 设 500 字符大约对应 125 tokens，留有余量。太小了语义不完整，太大了会被截断损失信息。实践中在 300-800 字符之间调优。

**Q: Chunk overlap 为什么要设？**

A: 防止问题刚好落在两个 chunk 的边界处，导致两边的 chunk 都不包含完整的上下文。overlap=50 意味着相邻 chunk 共享 50 个字符，边界处的信息至少在一个 chunk 里是完整的。

### 进阶概念

**Q: 什么是 Recall 和 Precision？在 RAG 场景下怎么理解？**

A:
- Recall = 被召回的相关文档数 / 总相关文档数。RAG 里，相关文档被召回的越多越好，漏了就没了。
- Precision = 被召回的相关文档数 / 总召回数。召回的文档里，不相关的结果越少越好，浪费 LLM 上下文窗口。

**Q: Hit Rate 和 MRR 是什么？**

A:
- Hit Rate@k = 在 top-k 个结果中至少有一个相关文档的比例。衡量"搜没搜到"。
- MRR（Mean Reciprocal Rank）= 对每个 query，第一个相关文档排名的倒数取平均。如果第一个相关文档排第 1，RR=1；排第 3，RR=1/3。衡量"搜到的有多靠前"。

**Q: NDCG 是什么？和 MRR 的区别？**

A: NDCG（Normalized Discounted Cumulative Gain）考虑整个排序列表的质量，不只第一个相关文档。每个位置有增益（相关=1，不相关=0），位置越靠后增益折扣越大（除以 log 位置），最后除以理想排序的 IDCG 归一化。NDCG 能处理多个相关文档、能区分"相关结果在第2位"和"第5位"，比 MRR 更严格。

**Q: BM25 的公式是什么？参数 b 和 k1 的作用？**

A:

$$BM25(q, d) = \sum_{t \in q} IDF(t) \cdot \frac{tf(t, d) \cdot (k_1 + 1)}{tf(t, d) + k_1 \cdot (1 - b + b \cdot \frac{|d|}{avgdl})}$$

- **IDF(t)**：词 t 在所有文档中的逆文档频率，常见词 IDF 低
- **k1**：控制词频饱和曲线，默认 1.2-2.0，越大词频对分数影响越大
- **b**：长度归一化系数，0 表示不归一化，1 表示完全归一化，默认 0.75

**Q: RRF 公式为什么有效？**

A:

$$RRF(d) = \sum_{r \in R} \frac{1}{k + rank_r(d)}$$

每个结果的最终分数 = 它在每条路上的排名位置的倒数之和。k 通常取 60。这个公式有效的原因是：如果一个结果在两条路上排名都靠前（比如 dense 第 2，sparse 第 3），它的总分就高；如果只在一条路上高（dense 第 1，sparse 第 50），总分中等。天然对"两路都认可"的结果加权。

**Q: 什么是 Chunk 策略的"最优"？有没有统一的最优策略？**

A: 没有统一最优，取决于数据类型和下游任务。代码场景适合 Recursive（在函数/类边界切），法律文档适合按章节切，学术论文适合按段落切。所以设计成可切换的策略模式，针对不同场景调优。

---

## 第三部分：Agent 八股文

### 基础概念

**Q: 什么是 AI Agent？和 LLM 有什么区别？**

A: LLM 是被动的文本生成器——你输入 prompt，它输出回答。Agent 是主动的决策者——它有自己的目标，可以使用工具，可以做多步推理，可以与环境交互。简单说，LLM 是"大脑"，Agent 是"大脑 + 手 + 眼睛"。

**Q: ReAct 模式是什么？和 Chain-of-Thought 有什么区别？**

A: CoT 只让 LLM 逐步推理但不行动（只说不做）。ReAct 在推理的同时可以采取行动并观察结果（边说边做）。ReAct = Reasoning + Acting。论文证明 ReAct 在需要外部知识的任务上显著优于 CoT，因为 Agent 可以实时获取信息来支撑推理。

**Q: Agent 的组成部分有哪些？**

A: 通常包括：
1. **Profile**：Agent 的身份和角色定义
2. **Memory**：短期（上下文窗口）和长期（外部存储）
3. **Planning**：将大目标分解成子任务
4. **Tool Use**：调用外部工具获取信息或执行动作
5. **Reflection**：评估自己的输出并修正

**Q: Function Calling 和 Tool Calling 的区别？**

A: 本质上是一回事。OpenAI 叫 Function Calling，Claude 叫 Tool Use，都是让 LLM 输出结构化的工具调用请求（JSON 格式），而不是自然语言。后者更容易程序化解析和执行。

### 进阶概念

**Q: 什么是 Harness？**

A: Agent Harness 是 Agent 的运行框架，负责管理 Agent 的整个生命周期——接收输入、维护状态、调用工具、记录轨迹、评估结果。它包括了 prompt 管理、工具注册、会话管理、日志记录和评测能力。好的 Harness 应该不依赖具体的 LLM 和具体的工具集，具有可插拔性。

**Q: 什么是 Agent 评测的难点？**

A:
1. **结果不确定性**：同一条 prompt 问两次可能得到不一样的答案（我用 temperature 0.3，实测同题重跑结果会变）
2. **多步依赖**：中间某步失败，最终结果可能是"虽然中间错了但最后对了"或"虽然中间对了但最后错了"
3. **难以自动化**：开放式回答没有标准答案，关键词匹配太死、LLM 裁判有偏差
4. **Reward Hacking**：Agent 可能用"作弊"的方式达到评测目标（比如直接读评测集的答案）

**Q: LangGraph 和直接写 ReAct 循环有什么区别？**

A: LangGraph 把 Agent 的状态流转建模成图（Graph），节点是状态（State），边是状态转移。它封装了状态管理、条件跳转、人机交互等。优点是复用性强，缺点是黑盒多——出 bug 时很难追踪。手写 ReAct 循环代码量多一些，但每一步都是显式的，调试和面试讲起来都更可控。

**Q: 什么是 Plan-and-Execute 模式？**

A: Agent 不是边做边想，而是先规划出一系列步骤，然后再逐步执行。适合复杂任务。缺点是规划阶段可能规划错误的方向，且无法利用执行中获取的新信息做动态调整。所以也有 RePlan 的变体——先规划，执行中定期重新规划。

**Q: Agent 的"记忆"有哪几种？你项目里用了哪些？**

A: 通常分短期和长期。短期记忆就是 LLM 的上下文窗口——我项目里把对话历史拼进 messages 一起送 LLM。长期记忆需要外部存储——我项目里把对话存进 MySQL 的 messages 表，agent_logs 表存决策链路，可以跨会话恢复。Redis 可以加速活跃会话的最近 N 轮。向量库可以存"语义记忆"，按相关性召回历史。

---

## 第四部分：LLM 八股文

**Q: GPT 的生成过程是怎样的？**

A: 自回归生成。给定一段文本，模型预测下一个 token 的概率分布，然后采样或贪心地选取一个 token 追加到文本后面，再预测下一个，直到遇到终止 token 或达到长度限制。

**Q: Temperature、Top-p、Top-k 分别控制什么？**

A:
- **Temperature**：控制概率分布的"尖锐程度"。温度越低，高概率词的占比越大（更确定），温度越高，低概率词也有机会被选到（更多样）。
- **Top-p (Nucleus Sampling)**：只从累积概率达到 p 的最小 token 集合里采样。p=0.9 就选累积概率前 90% 的 token。
- **Top-k**：只从概率最高的前 k 个 token 里采样。

通常组合使用：Top-p 和 Top-k 先过滤候选集，Temperature 再调整分布，最后采样。

**Q: Prompt Engineering 有哪些常用技巧？**

A:
1. **Role Prompting**：给 LLM 一个身份（"你是资深 Python 工程师"）
2. **Few-shot**：给几个输入输出示例（我的 ReAct prompt 里就有一个完整的示例对话）
3. **Chain-of-Thought**：让 LLM 逐步推理
4. **Structured Output**：指定输出格式（JSON、XML）
5. **Negative Prompt**：告诉 LLM 不要做什么
6. **System Prompt**：设定全局规则和约束
7. **分隔符**：用 ``` 或 === 分隔用户输入和指令，防注入

**Q: 什么是 System Prompt 和 User Prompt 的区别？**

A: System Prompt 设定 LLM 的行为准则（"你是助手"、"不要做"、"格式要求"），通常用户不可见。User Prompt 是用户的具体输入。大多数开源模型把 System Prompt 作为消息序列的第一条，跟 User Message 在底层是一样的，只是在 API 层面做了区分。

**Q: 什么是 Context Window？超长上下文会有什么问题？**

A: Context Window 是 LLM 一次能处理的最大 token 数。超长上下文的问题：
1. **Lost in the Middle**：模型更关注两端的内容，中间部分容易被忽略
2. **计算成本高**：注意力机制复杂度是 O(n²)，token 数翻倍，计算量翻四倍
3. **Response 变慢**：首 token 延迟随上下文长度增加

**Q: 什么是 Token？中文和英文的区别？**

A: Token 是模型处理文本的最小单位。英文平均一个词 ~1.3 token，中文平均一个字 ~1-2 token。所以同样的内容，中文消耗的 token 数通常是英文的 1.5-2 倍。这也是为什么中文场景下 context window 更容易用完。

**Q: 你对 SFT 和 RLHF 了解吗？**

A: SFT（Supervised Fine-Tuning）是用标注好的对话数据对预训练模型做有监督微调，让模型学会遵从指令的格式。RLHF（Reinforcement Learning from Human Feedback）是在 SFT 基础上，用人类偏好对模型的输出做排序训练，让模型学会"什么回答更好"。RLHF 通常有三步——SFT → Reward Model 训练 → PPO 强化学习。

---

## 第五部分：LangChain / LangGraph 八股文

**Q: LangChain 的核心组件有哪些？**

A:
1. **Models**：LLM 的抽象统一接口（OpenAI、Claude、Ollama 等）
2. **Prompts**：模板管理和动态构建
3. **Chains**：将多个步骤串联起来
4. **Agents**：让 LLM 自主选择和执行工具
5. **Retrievers**：检索外部知识
6. **Memory**：对话历史管理
7. **Callbacks**：执行过程中的事件钩子

**Q: LCEL (LangChain Expression Language) 是什么？**

A: LCEL 是用 `|` 操作符把 LangChain 组件串联起来的语法。`chain = prompt | model | output_parser`。它的优势在于自动处理流式输出、异步调用、重试和 fallback，不需要开发者自己写这些样板代码。

**Q: LangChain 的 Memory 有哪些类型？**

A:
1. **ConversationBufferMemory**：存所有历史消息，最简单但最占上下文
2. **ConversationBufferWindowMemory**：只存最近 N 轮
3. **ConversationSummaryMemory**：LLM 定期对历史做摘要，用摘要替代原始消息
4. **ConversationSummaryBufferMemory**：混合——在 token 数阈值内用原始消息，超出后变摘要
5. **VectorStoreRetrieverMemory**：把历史做向量搜索，只找回相关的历史

**Q: LangGraph 的核心概念是什么？**

A: LangGraph 的核心是 StateGraph。
- **Node**：执行单元（可以是一个函数、一个 chain、一个模型调用）
- **Edge**：节点间的连接
- **State**：全局状态字典，所有节点共享
- **Conditional Edge**：根据条件跳转到不同节点（比如"LLM 是否已给出最终答案"）

Agent 在 LangGraph 里的实现：一个循环，节点是 LLM → Tool → LLM → Tool，边是条件判断（"是否需要继续"）。

**Q: LangChain 的 Agent 和直接调 LLM API 自己实现的 Agent 有什么区别？**

A: LangChain Agent 封装了 prompt 构建、tool 解析、执行循环、错误重试。优点是开箱即用，缺点是调试困难、依赖重、prompt 不可见。自己实现的 Agent 代码量多一两倍，但每一步都是显式的，prompt 完全可控，面试里能讲清楚"为什么这里要这样设计"。我项目里还用到了 LangChain 的 Chroma 封装和文本 splitter，但不是整个 Agent 套 LangChain——这样既能讲原理，又能说明"知道怎么用现成库"。

---

## 第六部分：Python 后端八股文

**Q: `__init__.py` 的作用是什么？**

A: 把目录标记为 Python 包。Python 3.3+ 之后支持隐式命名空间包（没有 `__init__.py` 也可以），但显式加上可以控制 `from package import *` 的行为（`__all__`），以及执行包级别的初始化代码。

**Q: `__name__ == "__main__"` 的原理？**

A: 每个 Python 模块都有一个 `__name__` 属性。当模块被直接运行（`python module.py`）时，`__name__` 被设为 `"__main__"`。当模块被 import 时，`__name__` 设为模块名。所以这个判断可以用来写只有直接运行时才执行的代码（如测试）。

**Q: 什么是 GIL？对并发有什么影响？**

A: GIL（Global Interpreter Lock）是 CPython 的一个互斥锁，保证同一时刻只有一个线程在执行 Python 字节码。这意味着多线程不能利用多核 CPU 做并行计算。对于 I/O 密集型任务（如网络请求、数据库查询），多线程仍然有效，因为线程在等待 I/O 时会释放 GIL。对于 CPU 密集型任务，多线程反而会变慢，应该用多进程或 asyncio。

**Q: async/await 是怎么工作的？**

A: `async def` 定义协程函数，调用它返回一个协程对象。`await` 挂起当前协程，让出事件循环，等待被 await 的对象完成后再恢复。事件循环（event loop）维护一个任务队列，轮询哪个协程可以继续执行。这样在等待 I/O 时，单线程就可以处理其他请求。

**Q: 异步代码里可以做 `time.sleep()` 吗？**

A: 不行。`time.sleep()` 是同步阻塞，会阻塞整个事件循环线程。应该用 `asyncio.sleep()`，它会挂起当前协程但让事件循环继续处理其他任务。同理，同步的文件读写、数据库操作在异步代码里也会阻塞，需要用专门的异步库（aiomysql、aiofiles 等）。

**Q: `asyncio.to_thread` 是干什么的？你项目里怎么用的？**

A: `asyncio.to_thread(fn, args)` 把一个同步函数丢到线程池里执行，返回一个可 await 的协程。这样同步的、会阻塞的调用（比如 Chroma 检索、LLM 请求）不会卡住事件循环。我项目里 Agent 的同步 `harness.run()` 就是用 `await asyncio.to_thread(harness.run, req.message)` 跑的。要注意：被丢进线程的代码里不能再用 `asyncio.create_task()`（没有事件循环），这是我踩过的坑。

**Q: Python 的装饰器原理是什么？**

A: 装饰器是一个函数，接收一个函数作为参数，返回一个新的函数。`@decorator` 语法糖等价于 `func = decorator(func)`。常见应用：日志、鉴权、计时。装饰器可以有参数（两层嵌套），也可以作为类实现（`__call__` 方法）。

**Q: `yield` 和 `yield from` 的区别？**

A: `yield` 挂起当前函数，返回一个值给调用者，下次调用 `next()` 时从挂起处继续。`yield from` 把一个子生成器"委托"给当前生成器，子生成器的所有值直接传给调用者。在 FastAPI 的依赖注入中，`yield` 前后的代码分别对应"启动"和"清理"逻辑。

**Q: Pydantic 的 `BaseModel` 和 Python 的 `dataclass` 有什么区别？**

A: dataclass 只做数据容器 + 自动生成 `__init__`、`__repr__` 等。Pydantic 的类型验证（类型不对直接报错）、序列化/反序列化（`.model_dump()`、`.model_validate()`）、JSON schema 生成、配置管理（BaseSettings），这些 dataclass 都没有。API 开发场景下 Pydantic 更强大。

**Q: 你用过哪些 Python 设计模式？**

A:
- **工厂模式**：CodeChunker 根据 strategy 创建不同分块器
- **策略模式**：多种分块/检索策略可切换
- **依赖注入**：FastAPI 的 `Depends(get_db)` 注入数据库会话
- **单例模式**：settings 实例全局唯一
- **适配器模式**：Chroma 的搜索接口被统一到 DenseRetriever 后面
- **模板方法/抽象基类**：Tool 抽象基类定义接口，子类实现 execute

---

## 第七部分：MySQL 八股文

**Q: 索引的原理是什么？B+ 树有什么特点？**

A: 索引的核心是 B+ 树。特点：
- 所有数据存在叶子节点，内部节点只存键值
- 叶子节点之间有指针连接，形成有序链表，方便范围查询
- 树的高度通常 3-4 层，查询复杂度 O(log n)
- 相比 B 树，B+ 树的非叶子节点不存数据，可以存更多键，树更矮

**Q: 聚簇索引和非聚簇索引的区别？**

A: InnoDB 的主键索引是聚簇索引——叶子节点直接存整行数据。二级索引（非聚簇索引）的叶子节点存主键值，需要回表查询。所以主键查询比普通字段查询快。一张表只能有一个聚簇索引。

**Q: 什么情况下索引会失效？**

A:
1. 对索引列使用函数：`WHERE DATE(create_at) = '2024-01-01'`
2. 隐式类型转换：`WHERE varchar_col = 123`
3. 前导模糊查询：`WHERE name LIKE '%keyword'`
4. OR 条件里有一个非索引列
5. 组合索引没用到最左前缀

**Q: 事务的 ACID 特性是什么？**

A:
- **A (Atomicity)**：原子性，事务内的操作要么全做要么全不做
- **C (Consistency)**：一致性，事务前后数据状态一致
- **I (Isolation)**：隔离性，并发事务互不干扰
- **D (Durability)**：持久性，提交后数据不丢失

**Q: 四种隔离级别及解决的问题？**

A:
1. **Read Uncommitted**：可能读到未提交的数据（脏读）
2. **Read Committed**：避免脏读，但可能不可重复读（同一条语句多次执行结果不同）
3. **Repeatable Read**：避免不可重复读，但可能幻读（MySQL InnoDB 默认级别）
4. **Serializable**：最高级别，串行化执行，性能最差

**Q: SQLAlchemy N+1 问题是什么？怎么解决？**

A: 查询主表 N 条记录后，又逐条查询每条记录的关联表，导致 1 + N 次查询。解决：
- 使用 `joinedload()`：一次性 JOIN 查询
- 使用 `subqueryload()`：子查询方式加载关联
- 使用 `selectinload()`：WHERE IN 方式批量查询

**Q: `VARCHAR` 和 `TEXT` 的区别？**

A: VARCHAR 最大 65535 字节，可以在行内存储，可以建索引。TEXT 最大 65535 字符（约 64KB），超长时存在外部存储页，需要额外 I/O，不能有默认值，建索引需要指定前缀长度。日常短文本用 VARCHAR，长内容用 TEXT。我项目里消息内容和检索日志用 TEXT，session_id 等短字段用 VARCHAR。

**Q: 你项目里 MySQL 有哪些表？**

A: 核心的有：users（用户）、conversations/messages（对话会话与消息，存多轮上下文）、agent_logs（Agent 决策链路：thought/action/observation）、retrieval_logs（混合检索的完整链路打点）、query_rewrites（HyDE 改写记录）、evaluation_runs（消融实验结果）、feedbacks（用户点赞点踩）、index_versions（索引版本）。这些审计表让评估和数据复盘有据可查。

---

## 第八部分：Redis 八股文

**Q: Redis 支持哪些数据类型？**

A:
1. **String**：字符串、数字（INCR/DECR）
2. **List**：列表，左右 push/pop（LPUSH/RPOP，可实现队列）
3. **Set**：无序集合，去重、交集并集
4. **ZSet (Sorted Set)**：有序集合，每个成员有 score（延迟队列、排行榜）
5. **Hash**：字典结构（存对象、session 数据）
6. **Stream**：消息队列（类似 Kafka）

**Q: Redis 缓存常见问题——缓存穿透、缓存击穿、缓存雪崩？**

A:
- **缓存穿透**：查询一个不存在的数据，缓存和数据库都没有。大量请求直达数据库。解决：布隆过滤器或缓存空值（短 TTL）。
- **缓存击穿**：一个热点 key 过期，大量请求同时冲去数据库重建缓存。解决：互斥锁或永不过期 + 异步更新。
- **缓存雪崩**：大量 key 同时过期或 Redis 宕机。解决：过期时间加随机值、多级缓存、Redis 高可用。

**Q: Redis 的持久化方式有哪些？**

A:
- **RDB（快照）**：定期把内存数据 dump 到磁盘。优点：文件小、恢复快。缺点：数据可能丢失最后一次快照之后的数据。
- **AOF（Append Only File）**：记录每个写操作。优点：数据损失小（可配置 always/everysec/no）。缺点：文件大、恢复慢。
- **混合持久化（Redis 4.0+）**：RDB 做全量快照 + AOF 做增量日志。

**Q: Redis 为什么快？**

A:
1. **纯内存操作**，读写速度纳秒级
2. **单线程模型**，避免上下文切换和锁竞争（但 6.0+ 网络 I/O 多线程化了）
3. **I/O 多路复用**，用 epoll 同时监听多个 socket
4. **值类型简单**，针对每种数据结构做了专门优化

**Q: 什么是 Redis 的过期策略？**

A: 三种策略组合：
1. **定期删除**：每 100ms 随机抽一批设置了 TTL 的 key，过期则删
2. **惰性删除**：访问 key 时才检查是否过期
3. **内存淘汰**：内存不够时，按策略淘汰 key（LRU、LFU、TTL 等）

**Q: Redis 分布式锁怎么实现？**

A: `SET lock_key uuid NX EX 10`——如果 key 不存在则设置值（NX），自动过期 10 秒。解锁时用 Lua 脚本确保原子性：先检查锁的持有者是不是自己（uuid），再 DEL。这样防止误删别人的锁。

**Q: 你在项目里用 Redis 做了什么？**

A: 三件事：
1. **检索结果缓存**：同一 query 短时间内多次请求，直接从 Redis 返回，跳过 embedding + Chroma，TTL 5 分钟
2. **API 限流**：用 Redis ZSET 做滑动窗口限流，每个用户（或 IP）每分钟最多 60 次。ZSET 里存每个请求的时间戳，删窗口外记录后 zcard 统计，比固定窗口（INCR+EXPIRE）更平滑，不会在窗口边界产生突刺
3. **JWT 黑名单**：登出时把 token 存 Redis 标记为黑名单，TTL = 剩余有效期

---

## 第九部分：部署 & Docker 八股文

**Q: Docker 镜像和容器的区别？**

A: 镜像是构建好的包（只读模板），包含代码、运行时、依赖。容器是镜像的一个运行实例（可读写层）。类比：类（镜像）vs 对象（容器）。一个镜像可以启动多个容器。

**Q: Dockerfile 的多阶段构建是什么？**

A: 一个 Dockerfile 里写多个 FROM 语句。第一阶段用完整镜像编译/构建（带上所有构建工具），第二阶段用轻量运行镜像（只复制构建产物）。可以大幅减小最终镜像体积。我项目里编译 mysqlclient、chromadb 需要 build-essential 和 pkg-config，这些运行时不需要，理想情况下可以用多阶段构建去掉。

**Q: Docker Compose 和 Docker 的区别？**

A: Docker 管理单个容器。Compose 管理多个容器组成的"服务组"——定义在 docker-compose.yml 里，一条 `docker compose up --build` 就能全部启动，容器之间通过 service name 互相访问（比如 frontend 通过 `http://backend:8000` 访问后端，而不是 localhost）。

**Q: 你部署时遇到过什么坑？**

A: 六个：
1. **容器内 localhost 不通**：frontend 里写死 `127.0.0.1:8000`，在容器里指向前端自己。解法是把 API_BASE 改成环境变量，compose 里注入 `http://backend:8000/api`。
2. **mysqlclient 编译失败**：slim 镜像缺 pkg-config 和 libmysqlclient-dev，Dockerfile 里要 apt-get 安装。
3. **版本冲突**：chromadb 0.5 要求 bcrypt>=4.0.1，而 passlib 只兼容 bcrypt 3.x。最终抛弃 passlib，直接用 bcrypt 原生 API（hashpw/checkpw），问题消失。
4. **Docker 里 JWT_SECRET 为空**：config 默认值被清空后，compose 只传了 LLM_API_KEY 没传 JWT_SECRET，容器里会用空密钥签发 token，比硬编码更隐蔽。解法：compose 显式传 `JWT_SECRET: ${JWT_SECRET}`，并在 config 里做启动校验——密钥缺失或太短直接拒绝启动（fail fast）。
5. **测试污染开发数据库**：早期集成测试对默认 `code_assistant` 库执行过 `drop_all()`，把开发数据全删了。教训：测试必须用独立数据库（conftest 里固定 `MYSQL_DATABASE=code_assistant_test`），并设置 `SKIP_SECRET_VALIDATION` 跳过真实密钥校验。
6. **API Key 泄露进 Git 历史**：DeepSeek key 曾明文写在 config.py 里提交过。必须轮换 key（旧 key 即使删除代码引用仍有效），不能只删代码里的引用。

**Q: 测试里异步数据库操作怎么处理？**

A: 遇到过 `async fixture` 依赖 pytest-asyncio、以及跨事件循环复用 aiomysql 连接两个问题。正解是用 Starlette TestClient 的 `portal.call()`——在同步 fixture 里通过同一个事件循环执行异步建表/删表：
```python
with TestClient(app) as client:
    client.portal.call(_create_tables)
    yield client
    client.portal.call(_drop_tables)
```
这样建表、请求、删表都在同一个事件循环里，不会出现"连接属于另一个 loop"的错误。

**Q: CI/CD 的核心流程是什么？**

A: CI（持续集成）：代码 push 后自动跑测试、lint、构建镜像，确保新代码不破坏已有功能。CD（持续部署）：通过测试后自动部署到服务器。我项目里用 GitHub Actions 实现 CI——push 到 main 触发，起 MySQL 和 Redis services，装依赖后跑 pytest（密码哈希单测 + 鉴权 API 集成测试 + RRF 融合单测），覆盖注册/登录/刷新/登出/黑名单/401 全链路，通过才算绿。

---

## 第十部分：高频场景题

**Q: 如果你的 RAG 系统检索效果不好，怎么排查？**

A: 我会按链路逐层排查：
1. **分块质量**：检查是否有大块超过 token 限制被截断，是否有语义不连续的块
2. **query 质量**：用户 query 太短？尝试 query 改写看有没有提升
3. **embedding 质量**：在向量库中手动检索几个相关 query，看相似的代码是否在空间上靠近
4. **检索策略**：Dense 单路的召回率多少？加上 BM25 后提升了多少？
5. **重排序**：cross-encoder 是否把真正相关的结果排上来了？（我实测里它反而把正确结果排后面了）
6. **最终检查**：看 retrieval_logs 里的完整链路，每一步的结果

**Q: LLM 输出格式不稳定怎么办？**

A:
1. **结构化输出**：用 Pydantic 做输出解析，配合 `response_format={"type": "json_object"}`
2. **Few-shot 示例**：在 prompt 里给几个标准格式的例子（我的 ReAct prompt 里就有一个完整示例对话）
3. **多次重试**：解析失败时，把错误信息告诉 LLM 让它重试
4. **正则/解析器兜底**：我用花括号深度扫描解析嵌套 JSON，比简单正则鲁棒

**Q: 你的 Agent 如果陷入了死循环怎么办？**

A:
1. **最大轮次限制**：Harness 里设 `max_steps=6`，到了强制结束
2. **Token 预算**：累计 token 超限时停止并输出"无法在规定步骤内完成"
3. **重复检测**：如果 Agent 连续 N 步做出相同的动作，判定为循环，中断
4. **Fallback**：上述全部失败时，直接返回已有的检索结果作为最终答案

**Q: LLM 回答质量时好时坏怎么处理？**

A: 这是我们实测到的——同一个问题用 temperature 0.3 跑两次，结果会有波动。处理方式：① 降低 temperature 到 0.1-0.2 让输出更稳定（但要小心太机械）；② 评估时跑 3 次取平均，不要只看单次结果；③ 关键路径（如工具调用格式）用 few-shot 示例强化约束；④ 对最终答案做质量检查（比如检测是否包含"我不知道"式的敷衍回答）。

**Q: 你的 API Key 和 JWT 密钥是怎么管理的？**

A: 三件事：① 密钥只存在 `.env`，不进代码不进 Git（`.gitignore` 排除）；② 应用启动时校验——`LLM_API_KEY` 为空或 `JWT_SECRET` 少于 32 字符直接抛错拒绝启动（fail fast），避免用空密钥签发 token；③ API Key 一旦泄露必须轮换，不能只删代码里的引用。我踩过这个坑：DeepSeek key 曾明文进过 Git 历史，光删代码没用，必须去后台换新 key。

**Q: 多用户场景下，你怎么防止 A 用户看到 B 用户的数据？**

A: 分两层做隔离。第一层是**会话隔离**：Conversation 和 Message 表都带 `user_id`，查询强制按 `(user_id, session_id)` 过滤，数据库层还有联合唯一约束兜底。第二层是**知识库隔离**：用户上传的每个 chunk 写入 `owner_id` 元数据，检索时用 Chroma 的 metadata filter `{"source_type":"user_upload","owner_id":N}` 在检索端就过滤掉别人上传的内容，而不是把结果拉回来再过滤。前端每个用户登录生成独立的随机 session_id，不共用。

**Q: 你的测试会污染开发数据吗？怎么保证的？**

A: 踩过坑。早期集成测试对默认 `code_assistant` 库执行过 `drop_all()`，把开发数据全删了。之后用 conftest.py 把所有测试环境变量集中管理，`MYSQL_DATABASE` 固定指向独立的 `code_assistant_test` 库，CI 的 MySQL service 也建同样的测试库。这样测试跑一百遍也不会碰开发数据。测试里异步数据库操作用 `TestClient.portal.call()` 在同一个事件循环里执行建表/删表。

**Q: 你们为什么把系统语料和用户上传分开放？**

A: 两类语料用途完全不同。系统 TinyDB 语料是 Agent 回答问题的知识源，所有用户共享；用户上传是个人私有内容。如果不分开，A 用户上传的代码会被 B 用户搜到（越权），而且用户上传内容质量参差，会污染系统检索结果。我用 `source_type` 元数据区分，检索时按需过滤——搜系统走 `/api/search`（只查 system），搜自己的上传走 `/api/upload/search`（强制 owner_id）。这是数据边界意识，AI 应用很容易在这里出事故。

---

## 第十一部分：文件上传 & 多模态处理

**Q: 用户上传文件你怎么处理？**

A: 当前实现了代码/文本类文件（.py / .js / .md / .txt）的上传：校验扩展名 → 读取 UTF-8 内容 → 复用已有的 chunker 分块 → embedding 存进向量库，并给 chunk 打上 `source_type="user_upload"` 和 `owner_id=当前用户` 两个元数据标记。**上传后走的是和主仓库完全相同的 RAG 管道**——不单独写解析逻辑，只是多了一步"文件读入"。这样加新格式只需加一个读取 parser，核心 RAG 代码零改动，体现了系统可扩展性。同时 owner_id 标记让每个用户的上传内容在检索端隔离，互不可见。

**Q: 上传的文件和主仓库的索引是怎么隔离和合并的？**

A: 三层隔离：
1. **系统 vs 用户**：系统 TinyDB 语料打 `source_type="system"` 标，用户上传打 `source_type="user_upload"` 标。search 接口和 Agent 工具默认只搜系统语料（`where={"source_type":"system"}`），用户上传不进主检索链路。
2. **用户 vs 用户**：上传 chunk 额外写入 `owner_id=current_user.id`。检索用户上传内容时用 Chroma metadata filter `{"source_type":"user_upload","owner_id":N}`，在检索端就过滤掉其他用户的内容，而不是返回后再过滤。这是防止越权的关键。
3. **接口隔离**：搜系统代码走 `/api/search`，搜自己的上传走 `/api/upload/search`（服务端强制 owner_id），两条链路互不交叉。
底层共用一个向量库，靠 metadata 区分。设计上预留了独立 collection 的方案——如果量大了再拆。

**Q: 为什么要做文件上传这个功能？**

A:
1. **展示系统可扩展性**：新文件格式只需加 parser，不碰核心 RAG 代码
2. **最直观的演示效果**：面试时现场上传一段代码 → 问问题 → Agent 实时检索回答，比干讲有说服力多
3. **也是 Agent 多模态处理意识的体现**（虽然当前聚焦文本，架构上留了 PDF/OCR 的扩展位）

**Q: 如果以后要支持 PDF 和图片，你会怎么设计？**

A: 设计一个 `FileParser` 分发器，根据扩展名把文件交给不同 parser：代码/文本直接读内容、PDF 用 PyMuPDF 提取文字层、图片用 Tesseract OCR。提取出文本后，后续管道完全复用（chunker → embedding → 向量库）。加新格式只加一个 parser 函数，这是标准的策略模式。

---

> 最后一条建议：
> 面试官问你项目的时候，**每一个回答都要以"我"开头**——"我设计了"、"我做了消融实验"、"我发现了"。
> 不要说"这个项目实现了"——那是抄的。说"我实现了"——才是你做的。
> 另外，**不要只背答案**。上面的每个"准备答案示例"（尤其是踩坑故事）都要能用你自己的话讲出来，讲到面试官能感觉到你真正做过。
