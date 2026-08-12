# Code Assistant Agent — 面试准备手册

> 适用方向：AI 大模型应用开发 / Agent 方向实习（非算法岗）
> 范围：项目拷打 + RAG + Agent + LLM 基础 + Python + Redis + MySQL + LangChain/LangGraph

> 使用原则：只把已实现且能现场解释、复现的能力说成“我做了”。评估数据、压测、PDF/OCR、反馈闭环等没有完成验证的内容，统一说成“当前限制 / 下一步”，不要包装成生产系统。

---

## 第一部分：项目拷打（模拟面试 Q&A）

### 一、项目总览

**Q: 介绍一下你这个项目。**

A: 这是一个智能代码助手 Agent。用户可以用自然语言问关于代码库（TinyDB 开源项目）的问题，Agent 通过 OpenAI-compatible Function Calling 自主选择搜索代码、解释函数或生成测试，再基于工具结果给出答案。整个过程有对话记录，支持多轮上下文。数据模型里预留了反馈表（点赞/点踩），作为后续优化方向的候选。

技术上它分成四层：
- **RAG 层**：多策略分块器把源码切成代码块，支持 Dense / BM25 检索、RRF 融合、HyDE 和可选重排。20 条检索测试集用于 Hit Rate、MRR、NDCG 回归；另提供可选 RAGAS 脚本，以 8 条带参考答案的题目补充评估上下文相关性和答案正确性。RAGAS 尚未跑出可复现数据，不对外宣称分数。
- **知识库边界**：TinyDB 与当前项目源码分别使用独立的 Chroma collection 和 BM25 Redis key；API 与 Agent 在请求开始时固定一个知识库，会话历史也按知识库与 session 隔离，不混检两个代码库。
- **Agent 层**：自研轻量 Function Calling Harness，管理工具 schema、循环控制和调用轨迹；工具参数经 Pydantic 校验后执行，多轮对话历史持久化到数据库
- **API 层**：FastAPI 异步框架，JWT 鉴权 + Redis 黑名单登出，Redis 滑动窗口限流，文件上传索引
- **部署层**：提供 Docker Compose 编排（MySQL + Redis + 后端 + 前端），GitHub Actions 运行鉴权 API 集成测试和 RRF 单测。

**面试官追问：你遇到最大的技术挑战是什么？**

> 准备答案示例（任选一个真实经历）：
>
> **① LLM 输出格式不稳定导致 Agent 循环跑飞。** 早期版本从 LLM 文本中提取 Action JSON，嵌套参数和格式漂移都会让解析失败。后来将协议改为 OpenAI-compatible Function Calling：模型返回 `tool_calls`，Harness 根据静态工具白名单找到工具，再用 Pydantic 校验 JSON 参数后执行。这让我意识到：**Agent 的可靠性瓶颈往往不在 LLM 智商，而在工具协议和服务端校验**。
>
> **② 评估全 0 分，排查发现是 Windows 路径分隔符。** 消融实验第一次跑出来 Hit Rate 全是 0，我一度以为是检索坏了。后来打印诊断才发现：Windows 上 `os.path.relpath` 返回 `tinydb\database.py`（反斜杠），而测试集里写的是 `tinydb/database.py`（正斜杠），字符串匹配永远失败。修法是在指标函数里统一 `replace("\\", "/")`。这个坑说明：**评估代码的细节（路径、编码）往往比算法本身更容易出错**。

---

### 二、RAG 相关

**Q: 为什么选 all-MiniLM-L6-v2 而不是 OpenAI 的 embedding？**

A: 两个原因。第一，本地模型不需要网络调用和 API Key，开发迭代快，面试演示时也不依赖网络。第二，它体积和推理成本较低，适合作为这个项目的本地基线。384 维并不天然代表“对代码检索足够好”，是否换更适合代码/中文的 embedding 必须由测试集验证；切换模型名后还必须全量重建向量索引，不能只改一行配置。

**Q: 三种分块策略你怎么选的？给我讲讲对比结果。**

A: 当前实现提供 Recursive、Semantic 和 Token 三种策略。我先按代码结构选择 Recursive 作为默认：它优先利用空行和 def/class 边界，较少截断函数语义；Semantic 块更大，Token 块更均匀但更可能切开逻辑。当前参数是 chunk_size=500、overlap=50。**我还没有完成三种策略在同一测试集上的可复现实验，因此不会把这个选择说成已被数据证明的最优方案。**

**Q: 混合检索是怎么做的？**

A: Dense 路用 all-MiniLM 把 query 转成 384 维向量，在 Chroma 做相似度搜索；Sparse 路用 rank_bm25 做关键词匹配。当前实现是**顺序**调用两条路，再将各自 top-10 用 RRF（Reciprocal Rank Fusion）融合，公式是 1/(k + rank)，k=60。它没有做 Dense/Sparse 并发；外层只用 `asyncio.to_thread` 避免同步检索阻塞 FastAPI 事件循环。RRF 的好处是不需要调权重，也不受两路分数尺度不同影响。

**Q: 消融实验的数据是什么？**

A: 我准备了 20 条中文 query，并为每条标注期望命中的源文件，用 Hit Rate、MRR、NDCG 评估检索。它适合先验证“目标文件是否被召回、排得是否靠前”，但样本很小，也不能证明最终回答正确。

`evaluation.py` 与线上检索一样通过 `SparseRetriever.from_redis()` 恢复由索引器从同一批 chunks 构建的 BM25 索引；索引缺失时会直接失败，避免把空 BM25 当成有效实验。最近一轮固定环境下，hybrid 的 Hit Rate 为 1.00、MRR/NDCG 为 0.59/0.58；dense-only 为 0.95、0.60/0.60。该结果仅对应这 20 条题目和当前 TinyDB 索引，报告时必须同时说明版本、配置和运行时间，不能外推成通用结论。

**Q: RRF 和加权融合有什么区别？为什么选 RRF？**

A: RRF 不需要调权重，公式决定了两个路的结果会自动平衡。加权融合需要人为设定 dense 占 0.7 还是 0.6，这个值不同场景下最优解不一样，调起来很麻烦。RRF 用 rank 位置而不是分数做融合，天然不敏感分数尺度——dense 返回的分数是 0 到 1 之间的，BM25 的分数可以到几十，加权融合根本不好加。RRF 就没有这个问题。

**Q: cross-encoder 和 bi-encoder 有什么区别？**

A: Bi-encoder 是 query 和 document 各自独立编码成向量，再算相似度；它可以离线建索引，适合召回。Cross-encoder 则把 query 和 document 拼在一起前向计算，通常更精细但慢得多，适合对少量候选精排。项目可选地对融合结果重排；系统语料最近重建后是 39 个 chunk，不能再使用“215 个块”这个过期数字。是否启用 reranker 要以修复后的同一测试集结果和延迟成本决定，而不是默认开启。

**Q: HyDE 查询改写是什么原理？**

A: HyDE（Hypothetical Document Embedding）的思路是：用户问题往往很短（比如"insert 方法怎么工作"），直接做 embedding 效果不好。先让 LLM 根据问题"猜"一段理想的代码长什么样，然后用这段假代码去做 embedding 检索。假代码比原始问题更接近代码库的分布，所以检索效果更好。本质上是在做 query → document 的模态对齐。

---

### 三、Agent 相关

**Q: 你的 Agent 循环是怎么实现的？**

A: 当前是带原生工具调用协议的 ReAct 模式：
```
while True:
    ① 把系统提示词、对话历史、用户问题和工具 JSON Schema 一起送给 LLM
    ② LLM 通过 tool_calls 返回要调用的工具和 JSON 参数
    ③ Harness 按工具白名单查找工具，用 Pydantic 校验参数后执行
    ④ 将工具 Observation 作为 role=tool 消息追加到上下文
    ⑤ LLM 判断是否已经够信息给出最终答案
    ⑥ 如果够了，输出最终答案；否则回到①
```
每次工具调用的名称、已校验参数、执行状态和截断后的 Observation 会写入 `agent_logs`，并随当前响应返回给前端展示；不持久化模型原始 Thought/Chain of Thought。循环有 `max_steps=6` 兜底，同一轮相同工具与参数会被拒绝，防止无意义的重复调用。

**Q: Harness 是做什么的？为什么不用 LangGraph？**

A: Harness 是 Agent 的轻量运行框架，负责工具注册（Tool 实例放进 tool_map）、执行轨迹记录（agent_logs）和多轮历史恢复。当前只有三个工具和线性的 ReAct 循环，手写实现的状态和失败路径更容易观察；若后续出现分支工作流、人机审批、断点恢复或多 Agent 协作，我会优先评估 LangGraph。选择不是“自己写一定更好”，而是按当前复杂度取舍。

**Q: 三个工具是怎么注册到 Agent 的？**

A: 我定义了一个抽象基类 `Tool`，声明 name、description、args_model 和 execute。每个具体工具用 Pydantic 参数模型生成 JSON Schema；Harness 将 schema 放进 `tools` 请求字段，并维护 `tool_map` 白名单。模型只返回结构化 tool_calls，服务端再校验并执行。新增工具只需要定义参数模型、实现 execute 并加入列表。

**Q: 多轮对话是怎么实现的？**

A: 分两层。运行时 Harness 维护 `conversation_history`，每轮把 user/assistant 消息追加进 messages。持久化时，router 按 `(current_user.id, session_id)` 获取会话，从 messages 表恢复该会话历史，Agent 跑完后保存本轮消息。因此它支持**同一用户、同一 session_id** 跨请求和服务重启恢复上下文；它不是跨不同 session 自动恢复的“长期记忆”。

**Q: Agent 怎么评估的？**

A: 当前仓库有 8 条覆盖 TinyDB 核心模块的题目和参考答案。`run_agent_eval.py` 会运行轻量 smoke check，记录是否得到回答、工具调用次数和被拒绝调用次数；另有可选 RAGAS 脚本，基于生产混合检索路径用 LLM Judge 计算上下文相关性和答案正确性。RAGAS 尚未实际跑数，因此我不会声称已有平均语义分数或模块级结论。后续仍要补充结果持久化、失败样本人工抽检和答案要点覆盖率。

**Q: 你试过哪些 Agent 评估方案？为什么选语义相似度？**

A: 我会组合使用三类信号，而不是把 embedding 相似度当作真值：关键词/断言适合检查硬性要点，语义相似度能容忍表达差异，带明确 rubric 和源码证据的 LLM 裁判适合抽样人工复核。当前已接入可选 RAGAS 脚本，指标是 `context_relevancy` 和 `answer_correctness`，并使用本地 embedding，避免评估时隐式调用另一家 embedding 服务；但它仍依赖付费 LLM Judge，且只有 8 条人工题，必须结合人工审阅，不能把单次分数当作真值。

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

A: 我选择 JWT 是因为 API 与 Streamlit 前端之间用 Bearer token 传递比较直接，也便于将鉴权校验放在多个后端副本中。需要说清的是：JWT 本身不保存登录 session，但本项目为了登出失效增加了 Redis 黑名单，所以并非“完全无服务端状态”。Cookie 也能做跨站配置，并不是天然不能用；这个项目选 JWT 是权衡，不是唯一正确方案。

**Q: 你做了哪些并发方面的考虑？**

A: 两点落地：第一，Redis 滑动窗口限流中间件。它把每次请求以“UUID member + 时间戳 score”写入 ZSET，删除窗口外记录后以 zcard 统计；有效 JWT 按用户限流，无效或匿名请求回退到 IP，每分钟 60 次。Redis 不可用时当前策略是放行并记录日志，这是可用性优先的降级，也意味着生产环境应配监控和 Redis 高可用。第二，Agent 的同步执行通过 `asyncio.to_thread` 放入线程池，避免阻塞 FastAPI 事件循环。

**Q: LLM 调用层是怎么封装的？**

A: `llm.py` 封装了 `call_llm` 和 `call_llm_with_messages`：① 由配置切换 DeepSeek / Ollama，并按需带 Bearer token；② 兼容 Ollama 的 `message.content` 与 OpenAI/DeepSeek 的 `choices[0].message.content`；③ 默认最多 3 次尝试，退避 1 秒、2 秒；④ 全部失败返回空串。当前限制是同步 httpx 调用和“空串”这个弱错误契约，调用方不一定能区分模型空答与请求失败；后续应改为显式错误结果和异步客户端。

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

A: Harness 是 Agent 的运行框架，负责把 prompt、工具注册、循环控制、会话历史和执行轨迹组织起来。这个项目中的 Harness 已实现工具映射、Function Calling 循环、历史恢复和 `agent_logs` 摘要记录；**评测不是 Harness 当前职责**，也还没有完全做到与具体 LLM、工具集解耦。面试时我会讲它是为理解和可观测性写的轻量实现，不把它夸成通用 Agent 框架。

**Q: 什么是 Agent 评测的难点？**

A:
1. **结果不确定性**：同一条 prompt 多次运行可能得到不一样的答案；当前调用 temperature=0.3，但还没有完成多次运行的统计验证
2. **多步依赖**：中间某步失败，最终结果可能是"虽然中间错了但最后对了"或"虽然中间对了但最后错了"
3. **难以自动化**：开放式回答没有标准答案，关键词匹配太死、LLM 裁判有偏差
4. **Reward Hacking**：Agent 可能用"作弊"的方式达到评测目标（比如直接读评测集的答案）

**Q: LangGraph 和直接写 ReAct 循环有什么区别？**

A: LangGraph 把 Agent 的状态流转建模成图（Graph），节点是状态（State），边是状态转移。它封装了状态管理、条件跳转、人机交互等。优点是复用性强，缺点是黑盒多——出 bug 时很难追踪。手写 ReAct 循环代码量多一些，但每一步都是显式的，调试和面试讲起来都更可控。

**Q: 什么是 Plan-and-Execute 模式？**

A: Agent 不是边做边想，而是先规划出一系列步骤，然后再逐步执行。适合复杂任务。缺点是规划阶段可能规划错误的方向，且无法利用执行中获取的新信息做动态调整。所以也有 RePlan 的变体——先规划，执行中定期重新规划。

**Q: Agent 的"记忆"有哪几种？你项目里用了哪些？**

A: 通常分短期和长期。短期记忆是当前上下文窗口，本项目把同一会话的历史拼进 messages；长期记忆可放在外部存储，本项目将 messages 和 agent_logs 写入 MySQL。这里要精确：当前只能按同一 `(user_id, session_id)` 恢复，**不能跨不同 session 自动恢复**，也没有实现 Redis 活跃会话缓存或向量语义记忆；后二者只是可选设计。

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
2. **Few-shot**：给几个输入输出示例；当前 Function Calling 版本依赖工具 schema 约束，尚未加入示例对话
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

A: 核心表有：users、conversations/messages、agent_logs、retrieval_logs、query_rewrites、evaluation_runs、feedbacks、index_versions。它们为会话、检索和索引版本预留了记录位置；但要区分“有表”与“形成闭环”：feedbacks 尚无 API/UI，Agent 评测尚无端到端 runner，搜索接口也还没有返回真实 latency。不能仅因有表就声称已完成数据驱动优化。

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
1. **检索结果缓存**：同一 query、top-k 和 metadata filter 组合短时间内多次请求，直接从 Redis 返回，跳过 embedding + Chroma，TTL 5 分钟。把 filter 放进缓存 key 是多用户隔离的必要条件，否则同一 query 可能串数据。
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

A: CI（持续集成）是在代码变更后自动执行校验；CD（持续部署）是在通过校验后自动部署。项目当前只实现了 CI，不含自动部署、lint 或镜像构建：push/PR 到 main 会启动 MySQL、Redis，运行密码哈希单测、鉴权 API 集成测试和 RRF 融合单测，覆盖注册、登录、刷新、登出、黑名单和 401。它还没有覆盖上传隔离、会话隔离、限流 429、完整 RAG 或 Docker 运行，因此绿灯不等于生产就绪。

---

## 第十部分：高频场景题

**Q: 如果你的 RAG 系统检索效果不好，怎么排查？**

A: 我会按链路逐层排查：
1. **分块质量**：检查是否有大块超过 token 限制被截断，是否有语义不连续的块
2. **query 质量**：用户 query 太短？尝试 query 改写看有没有提升
3. **embedding 质量**：在向量库中手动检索几个相关 query，看相似的代码是否在空间上靠近
4. **检索策略**：Dense 单路的召回率多少？加上 BM25 后提升了多少？
5. **重排序**：cross-encoder 是否把真正相关的结果排上来了？需要与不重排基线在同一测试集上比较指标和延迟，不能假定加了就会更好
6. **最终检查**：看 hybrid 检索产生的 retrieval_logs，核对两路候选、融合结果和记录的耗时；当前不是所有检索路径都完整打点。

**Q: LLM 输出格式不稳定怎么办？**

A: 当前使用 OpenAI-compatible Function Calling：模型通过 tool_calls 返回结构化调用，Harness 只允许静态注册的三个工具，并用 Pydantic 校验参数。无效 JSON、未知工具、不合法参数或同一轮相同参数的重复调用都不会执行，而是作为结构化错误 Observation 回传模型；循环仍有 `max_steps=6` 上限。供应商不支持原生工具调用时，才考虑受限的 JSON 输出降级方案。

**Q: 你的 Agent 如果陷入了死循环怎么办？**

A: 当前有两层硬保护：`max_steps=6` 的循环上限，以及同一轮按“工具名 + 规范化参数”计算的调用指纹，重复调用会被拒绝并把已有 Observation 回传模型。它们能阻止最常见的重复调用，但还没有 token/时间预算、跨轮语义级去重或回退答案策略，不能保证高质量终止。

**Q: LLM 回答质量时好时坏怎么处理？**

A: LLM 输出本身有随机性。当前调用固定 `temperature=0.3`，工具调用由 Function Calling schema 和服务端 Pydantic 校验约束，并未依赖 few-shot 固定工具格式；项目还没有完成“同题多次运行取均值”或自动答案质量检查。要降低波动，我会先固定模型版本、prompt 和检索索引，再对固定测试集多次运行并报告均值和方差；对工具调用优先收紧结构化约束，而不是只靠降低 temperature。

**Q: 你的 API Key 和 JWT 密钥是怎么管理的？**

A: 三件事：① 密钥只存在 `.env`，不进代码不进 Git（`.gitignore` 排除）；② 应用启动时校验——`LLM_API_KEY` 为空或 `JWT_SECRET` 少于 32 字符直接抛错拒绝启动（fail fast），避免用空密钥签发 token；③ API Key 一旦泄露必须轮换，不能只删代码里的引用。我踩过这个坑：DeepSeek key 曾明文进过 Git 历史，光删代码没用，必须去后台换新 key。

**Q: 多用户场景下，你怎么防止 A 用户看到 B 用户的数据？**

A: 分两层做隔离。第一层是**会话隔离**：Conversation 和 Message 表都带 `user_id`，查询强制按 `(user_id, session_id)` 过滤，数据库层还有联合唯一约束兜底。第二层是**知识库隔离**：用户上传的每个 chunk 写入 `owner_id` 元数据，检索时用 Chroma 的 metadata filter `{"source_type":"user_upload","owner_id":N}` 在检索端就过滤掉别人上传的内容，而不是把结果拉回来再过滤。前端每个用户登录生成独立的随机 session_id，不共用。

**Q: 你的测试会污染开发数据吗？怎么保证的？**

A: 踩过坑。早期集成测试对默认 `code_assistant` 库执行过 `drop_all()`，把开发数据全删了。之后用 conftest.py 把所有测试环境变量集中管理，`MYSQL_DATABASE` 固定指向独立的 `code_assistant_test` 库，CI 的 MySQL service 也建同样的测试库。这样测试跑一百遍也不会碰开发数据。测试里异步数据库操作用 `TestClient.portal.call()` 在同一个事件循环里执行建表/删表。

**Q: 你们为什么把系统语料和用户上传分开放？**

A: 两类语料用途完全不同。系统 TinyDB 语料是 Agent 回答问题的知识源，所有用户共享；用户上传是个人私有内容。如果不分开，A 用户上传的代码会被 B 用户搜到（越权），而且用户上传内容质量参差，会污染系统检索结果。我用 `source_type` 元数据区分，检索时按需过滤——搜系统走 `/api/search`（只查 system），搜自己的上传走 `/api/upload/search`（强制 owner_id）。这是数据边界意识，AI 应用很容易在这里出事故。

**Q: metadata 过滤已经做了，缓存会不会把 A 的结果给 B？**

A: 会，这是多租户检索容易漏掉的一层。当前 DenseRetriever 的 Redis key 包含 query、top-k 和按 key 排序后的 `where` filter；用户上传的 filter 含 `source_type=user_upload` 和 `owner_id`，所以不同用户不会命中同一缓存项。若缓存 key 只用 query，即使 Chroma 检索端过滤正确，缓存层仍会造成跨用户泄露。缓存隔离必须和数据库/向量库隔离一起设计。

**Q: 系统索引重建时，用户上传的数据会怎样？**

A: 系统语料、项目源码与用户上传已经使用独立的 Chroma collection：`system_code`、`project_code` 和 `user_uploads`。重建其中一个公开知识库只会删除它自己的 collection；上传检索还要求 `source_type=user_upload` 与当前 `owner_id` 的 metadata filter，因此重建公开索引不会删除用户向量，也不会跨用户召回。公开知识库由 `knowledge_base_id` 显式区分，并让 collection、BM25 key 和 API 查询范围都绑定该 ID；不能只靠给文档加一个 metadata。

**Q: 为什么把项目自身源码也做成一个知识库？如何避免污染 TinyDB 检索？**

A: 它让演示可以回答“Function Calling 如何落地”“BM25 如何和 Chroma 融合”等项目自身的实现问题，比只解释第三方 TinyDB 更贴近岗位。但我没有把两个仓库塞进同一 collection：`tinydb` 使用 `system_code`，`project` 使用 `project_code`，BM25 Redis key 也包含 collection 名。前端/API 先选择知识库，Agent 初始化时把工具绑定到该库；同一用户切库时，持久化 session 会加上知识库前缀。因此模型不能靠一次工具调用跨库检索，历史也不会串库。

**Q: 检索评估为什么不能只报一个很高的 Hit Rate？**

A: 首先，20 条 query 只适合快速回归，样本过小且都以“命中预期源文件”为标注，不能代表真实用户问题，也不评估 chunk 充分性和最终答案事实性。其次，评估实现必须与生产一致；当前检索评估已恢复索引器构建并缓存的 BM25 索引，索引缺失时会失败。正确做法仍是扩大并分层测试集，保留失败案例，并同时报告检索指标、引用正确性、工具调用成功率和人工抽检结果。

**Q: RAG / Agent 如何防提示注入和越权工具调用？**

A: 当前 Agent 的工具是静态注册的三个代码工具，主检索只读系统语料；生成的测试代码也不会由服务端执行。Function Calling 后，工具参数在服务端按 Pydantic schema 校验，未知工具不会执行。但这不等于完整解决提示注入：若未来增加写入或外部调用工具，还必须做按用户授权、显式确认和恶意输入回归测试。

**Q: 你的检索延迟指标可信吗？**

A: `hybrid_search` 会测量并写入 retrieval_logs，但 `/api/search` 当前固定返回 `latency_ms=0.0`，所以不能拿 API 响应字段去报告性能，也没有做并发压测或 P95/P99。面试时我会只说“内部 hybrid 路径有单次耗时记录”，并把端到端延迟、缓存命中率和分位数压测列为下一步，而不是伪装成已有 SLA。

**Q: Redis ZSET 限流已经是滑动窗口，为什么还需要 Lua？**

A: ZSET 能表达滑动窗口，但当前实现把删除旧记录、写入当前请求、计数和设置过期放在 pipeline 中；pipeline 减少网络往返，不等于整个“检查再写入”过程对并发请求原子。在临界并发下，多个请求可能都看到未超限再一起通过。下一步应把这四步放进 Lua 脚本，并明确“第 N 次是否拒绝”的顺序；还要为 429、匿名 IP 与已登录用户三种路径补集成测试。当前实现适合演示算法和基本保护，不能宣称严格配额。

---

## 第十一部分：文件上传 & 多模态处理

**Q: 用户上传文件你怎么处理？**

A: 当前实现了代码/文本类文件（.py / .js / .md / .txt）的上传：校验扩展名 → 读取 UTF-8 内容 → 复用已有 chunker 分块 → embedding 存进向量库，并给 chunk 打上 `source_type="user_upload"` 和 `owner_id=当前用户`。它复用了系统语料的**分块和 Dense 检索**路径，但没有把上传内容加入 BM25 或 Agent 主检索；上传内容要通过 `/api/upload/search` 单独查询。owner_id filter 让用户间内容在检索端隔离。至于新格式，目前仍需同时补 parser、扩展名白名单和测试，不能说“零改动”。

**Q: 上传的文件和主仓库的索引是怎么隔离和合并的？**

A: 三层隔离：
1. **系统 vs 用户**：系统 TinyDB 语料打 `source_type="system"` 标，用户上传打 `source_type="user_upload"` 标。search 接口和 Agent 工具默认只搜系统语料（`where={"source_type":"system"}`），用户上传不进主检索链路。
2. **用户 vs 用户**：上传 chunk 额外写入 `owner_id=current_user.id`。检索用户上传内容时用 Chroma metadata filter `{"source_type":"user_upload","owner_id":N}`，在检索端就过滤掉其他用户的内容，而不是返回后再过滤。这是防止越权的关键。
3. **接口隔离**：搜系统代码走 `/api/search`，搜自己的上传走 `/api/upload/search`（服务端强制 owner_id），两条链路互不交叉。
底层使用同一 Chroma 持久化目录，但采用独立 collection：`system_code` 存系统语料，`user_uploads` 存用户上传。系统索引重建仅删除 `system_code`，不会影响上传内容；metadata filter 仍是查询时的第二道隔离。

**Q: 为什么要做文件上传这个功能？**

A:
1. **展示数据边界**：上传内容不是混进公共语料，而是以 owner_id 和独立接口隔离
2. **最直观的演示效果**：面试时现场上传一段代码 → 调用 `/api/upload/search` 查询其中内容，能展示从上传、分块到受限检索的闭环
3. **明确能力边界**：它是文本/代码上传，不是多模态 Agent，也尚未接入 Agent 主对话链路

**Q: 如果以后要支持 PDF 和图片，你会怎么设计？**

A: 这是未来设计，不是当前实现。我会先定义清晰的 parser 接口：代码/文本直接读取，PDF 先用 PyMuPDF 提取文字层，扫描版再考虑 OCR。解析结果应保留页码/文件名等引用元数据，并设置文件大小、页数、解析超时和恶意文件防护。之后再进入现有 chunker 和索引流程；每加一种格式还要补白名单、失败处理和隔离测试，不能只加一个 parser 函数就宣称完成。

---

> 最后一条建议：
> 面试官问你项目的时候，**每一个回答都要以"我"开头**——"我设计了"、"我做了消融实验"、"我发现了"。
> 不要说"这个项目实现了"——那是抄的。说"我实现了"——才是你做的。
> 另外，**不要只背答案**。上面的每个"准备答案示例"（尤其是踩坑故事）都要能用你自己的话讲出来，讲到面试官能感觉到你真正做过。
