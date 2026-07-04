# Code Assistant Agent — 面试准备手册

> 适用方向：AI 大模型应用开发 / Agent 方向实习（非算法岗）
> 范围：项目拷打 + RAG + Agent + LLM 基础 + Python + Redis + MySQL + LangChain/LangGraph

---

## 第一部分：项目拷打（模拟面试 Q&A）

### 一、项目总览

**Q: 介绍一下你这个项目。**

A: 这是一个智能代码助手 Agent。用户可以用自然语言问关于代码库的问题，Agent 通过 ReAct 循环自主决定调用哪个工具（搜索代码、解释函数、生成测试），最终给出答案。整个过程有对话记录，用户可以点赞/点踩反馈。

技术上它分成四层：
- **RAG 层**：用多策略分块器把源码切成代码块，做混合检索（Dense + Sparse）+ RRF 融合 + cross-encoder 重排
- **Agent 层**：封装了一个轻量 Harness，管理 ReAct 循环和工具注册，决策链路完整存入 MySQL
- **API 层**：FastAPI 异步框架，JWT 鉴权，Redis 限流
- **部署层**：Docker 多容器编排，部署在 Railway

**面试官追问：你遇到最大的技术挑战是什么？**

> 准备答案示例：Chroma 多进程并发写入的问题。chromadb 默认的 SQLite 后端不支持并发写入，我需要在构建索引时加锁，或者在单进程里完成写入。最后我通过将索引构建隔离到独立进程解决。

---

### 二、RAG 相关

**Q: 为什么选 all-MiniLM-L6-v2 而不是 OpenAI 的 embedding？**

A: 两个原因。第一，本地模型不需要网络调用和 API Key，开发迭代快，面试演示时也不依赖网络。第二，对于代码检索场景，384 维的向量已经够用，我做了消融实验验证了 Recall@3 达到 0.91。如果生产环境需要更高精度，config.py 切换模型名一行就能换成 text-embedding-3-small。

**Q: 三种分块策略你怎么选的？给我讲讲对比结果。**

A: 我跑了一组对比实验：Recursive 策略产出 215 块（默认，平衡），Semantic 策略只产出 39 块（每块太大，超过 256 token 上限），Token 策略 299 块（切得太碎，会切断函数逻辑）。最终选 Recursive 作为默认，因为它优先在代码空行和 def/class 边界切分，保持了每块的语义完整性。

**Q: 混合检索是怎么做的？**

A: 同时跑两条路——Dense 路用 all-MiniLM 把 query 转成 384 维向量在 Chroma 里做余弦相似度搜索；Sparse 路用 BM25 做关键词匹配。两路各自返回 top-10 后，用 RRF（Reciprocal Rank Fusion）融合排序。公式是 $1/(k + rank)$，k 取 60。这样做的好处是不需要调权重。

**Q: 消融实验的数据是什么？**

A: 我构建了 30 个测试 query，手动标注了预期的命中文件。跑下来结果：
- Dense alone: Hit Rate 0.65, MRR 0.58
- + BM25 (RRF): Hit Rate 0.82 (+26%), MRR 0.74
- + Reranker: Hit Rate 0.91 (+11%), MRR 0.85

每一步都有明确的提升，验证了混合检索的必要性。

**Q: RRF 和加权融合有什么区别？为什么选 RRF？**

A: RRF 不需要调权重，公式决定了两个路的结果会自动平衡。加权融合需要人为设定 dense 占 0.7 还是 0.6，这个值不同场景下最优解不一样，调起来很麻烦。RRF 用 rank 位置而不是分数做融合，天然不敏感分数尺度——dense 返回的分数是 0 到 1 之间的，BM25 的分数可以到几十，加权融合根本不好加。RRF 就没有这个问题。

**Q: cross-encoder 和 bi-encoder 有什么区别？**

A: Bi-encoder 是 query 和 document 各自独立编码成向量，然后算余弦相似度。速度快，可以离线建索引，适合召回阶段。Cross-encoder 是把 query 和 document 拼在一起送进模型做一次前向传播，精度更高但慢很多，适合精排阶段。我的流程是：bi-encoder 从 215 个块里召回 top-10，cross-encoder 对这 10 个重新打分取 top-3。

**Q: HyDE 查询改写是什么原理？**

A: HyDE（Hypothetical Document Embedding）的思路是：用户问题往往很短（比如"insert"），直接做 embedding 效果不好。先让 LLM 根据问题"猜"一段理想的代码长什么样，然后用这段假代码去做 embedding 检索。假代码比原始问题更接近代码库的分布，所以检索效果更好。本质上是在做 query → document 的模态对齐。

---

### 三、Agent 相关

**Q: 你的 Agent 循环是怎么实现的？**

A: 标准 ReAct 模式：
```
while True:
    ① 把用户问题 + 历史 + 可用工具描述 拼成 prompt 送 LLM
    ② LLM 输出 Thought（思考）和 Action（要调用的工具 + 参数）
    ③ 执行工具，返回 Observation
    ④ Observation 追加到上下文
    ⑤ LLM 判断是否已经够信息给出最终答案
    ⑥ 如果够了，输出 Final Answer；否则回到①
```

每一步的决策链都存到 MySQL 的 retrieval_logs 表里。

**Q: Harness 是做什么的？为什么不用 LangGraph？**

A: Harness 是 Agent 的轻量运行框架——它负责三件事：工具注册、执行轨迹记录、批量评测。LangGraph 功能更强但封装太厚，面试时面试官一问"图状态怎么传递"就容易卡壳。我自己的 Harness 大约 80 行，每个方法都能讲清楚设计意图。而且架构上预留了 LangGraph 的接口，以后想换可以换。

**Q: 三个工具是怎么注册到 Agent 的？**

A: 每个工具定义为一个 ToolDef 结构：
```python
@dataclass
class ToolDef:
    name: str          # "search_code"
    description: str   # "搜索代码库中与...相关的代码"
    fn: Callable       # 实际的 Python 函数
```
Harness 内部维护一个 `tools: list[ToolDef]`，LLM 的 prompt 里会注入所有工具的 name 和 description，LLM 根据描述决定调哪个。

**Q: Agent 成功率怎么评估的？**

A: 定义了 20 个测试任务（比如"查找所有 insert 相关的方法"、"解释 Table 类的构造函数"），人工标注了预期行为。Harness 有 `evaluate()` 方法批量跑，然后算 Task Success Rate = 成功数 / 总数。消融实验也能对比不同 prompt 模板或不同 LLM 的成功率差异。

**Q: 用户反馈数据怎么用的？**

A: Feedback 表存了 message_id、rating（1 点赞 / -1 点踩）、可选评论文本。目前主要用来做 Agent 质量的粗略指标——点赞率 = 点赞数 / 总反馈数。如果时间充裕，可以把点踩的数据拿出来分析：哪些类型的问题 Agent 容易答错，针对性地优化 prompt。

---

### 四、架构与工程相关

**Q: 你为什么用 FastAPI 不是 Flask？**

A: FastAPI 原生支持异步，对于我这个项目来说很重要——Agent 循环可能涉及多次 LLM 调用，如果用 Flask 同步框架，每个请求都会阻塞住整个 worker 线程，并发能力差。FastAPI 基于 Starlette + Pydantic，自动生成 OpenAPI 文档，类型检查也更严格。

**Q: 异步 SQLAlchemy 和同步有什么区别？**

A: 核心区别在于数据库 I/O 是否阻塞事件循环。同步 SQLAlchemy 执行查询时，Python 线程会挂起等待数据库返回结果，如果此时有其他请求进来，只能等当前查询完成。异步 SQLAlchemy（通过 aiomysql 驱动）在等待数据库时让出事件循环，服务器可以处理其他请求，用更少的资源支持更多并发。

**Q: JWT 的黑名单是怎么实现的？**

A: JWT 的天然缺陷是一旦签发，在过期之前无法撤回。我用 Redis 做了一层黑名单：用户调用登出接口时，把该 token 的 jti（JWT ID）存入 Redis，TTL 设为 token 的剩余有效期。验证中间件里多一步"检查 jti 是否在 Redis 黑名单中"。

**Q: 你为什么不自己做登录 session 用 Cookie 而要选 JWT？**

A: 两个原因。第一，JWT 是无状态的，服务端不需要存 session，方便水平扩展——部署多个副本时不需要共享 session 存储。第二，我这个项目既有后端 API 又有 Streamlit 前端，JWT 可以方便地在不同客户端之间传递（API 请求头 Bearer token），而 Cookie 受同源策略限制。

**Q: 你做了哪些并发方面的考虑？**

A: 三点：第一，SQLAlchemy 连接池配置了 pool_size=10，max_overflow=20，避免频繁创建销毁数据库连接。第二，Redis 滑动窗口限流，防止单个用户的请求打满 DeepSeek API 的频率限制。第三，请求耗时监控中间件，记录每个端点的响应时间，帮助发现慢查询。

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
1. **结果不确定性**：同一条 prompt 问两次可能得到不一样的答案
2. **多步依赖**：中间某步失败，最终结果可能是"虽然中间错了但最后对了"或"虽然中间对了但最后错了"
3. **难以自动化**：有些任务需要人工判断是否成功
4. **Reward Hacking**：Agent 可能用"作弊"的方式达到评测目标（比如直接读评测集的答案）

**Q: LangGraph 和直接写 ReAct 循环有什么区别？**

A: LangGraph 把 Agent 的状态流转建模成图（Graph），节点是状态（State），边是状态转移。它封装了状态管理、条件跳转、人机交互等。优点是复用性强，缺点是黑盒多——出 bug 时很难追踪。手写 ReAct 循环代码量多一些，但每一步都是显式的，调试和面试讲起来都更可控。

**Q: 什么是 Plan-and-Execute 模式？**

A: Agent 不是边做边想，而是先规划出一系列步骤，然后再逐步执行。适合复杂任务。缺点是规划阶段可能规划错误的方向，且无法利用执行中获取的新信息做动态调整。所以也有 RePlan 的变体——先规划，执行中定期重新规划。

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
2. **Few-shot**：给几个输入输出示例
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

A: LangChain Agent 封装了 prompt 构建、tool 解析、执行循环、错误重试。优点是开箱即用，缺点是调试困难、依赖重、prompt 不可见。自己实现的 Agent 代码量多一两倍，但每一步都是显式的，prompt 完全可控，面试里能讲清楚"为什么这里要这样设计"。

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

A: VARCHAR 最大 65535 字节，可以在行内存储，可以建索引。TEXT 最大 65535 字符（约 64KB），超长时存在外部存储页，需要额外 I/O，不能有默认值，建索引需要指定前缀长度。日常短文本用 VARCHAR，长内容用 TEXT。

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
2. **API 限流**：用 INCR + EXPIRE 做滑动窗口计数，每个 IP 每分钟最多 60 次
3. **JWT 黑名单**：登出时 token 的 jti 存 Redis 标记为黑名单

---

## 第九部分：部署 & Docker 八股文

**Q: Docker 镜像和容器的区别？**

A: 镜像是构建好的包（只读模板），包含代码、运行时、依赖。容器是镜像的一个运行实例（可读写层）。类比：类（镜像）vs 对象（容器）。一个镜像可以启动多个容器。

**Q: Dockerfile 的多阶段构建是什么？**

A: 一个 Dockerfile 里写多个 FROM 语句。第一阶段用完整镜像编译/构建（带上所有构建工具），第二阶段用轻量运行镜像（只复制构建产物）。可以大幅减小最终镜像体积。

**Q: Docker Compose 和 Docker 的区别？**

A: Docker 管理单个容器。Compose 管理多个容器组成的"服务组"——定义在 docker-compose.yml 里，一条 `docker compose up -d` 就能全部启动，容器之间通过 service name 互相访问。

**Q: CI/CD 的核心流程是什么？**

A: CI（持续集成）：代码 push 后自动跑测试、lint、构建镜像，确保新代码不破坏已有功能。CD（持续部署）：通过测试后自动部署到服务器。我项目里用 GitHub Actions 实现——push main 分支时触发测试，通过后构建镜像并推到 Docker Hub，Railway 检测到新镜像后自动部署。

---

## 第十部分：高频场景题

**Q: 如果你的 RAG 系统检索效果不好，怎么排查？**

A: 我会按链路逐层排查：
1. **分块质量**：检查是否有大块超过 token 限制被截断，是否有语义不连续的块
2. **query 质量**：用户 query 太短？尝试 query 改写看有没有提升
3. **embedding 质量**：在向量库中手动检索几个相关 query，看相似的代码是否在空间上靠近
4. **检索策略**：Dense 单路的召回率多少？加上 BM25 后提升了多少？
5. **重排序**：cross-encoder 是否把真正相关的结果排上来了？
6. **最终检查**：看 retrieval_logs 里的完整链路，每一步的结果

**Q: LLM 输出格式不稳定怎么办？**

A: 
1. **结构化输出**：用 Pydantic 做输出解析，配合 `response_format={"type": "json_object"}`
2. **Few-shot 示例**：在 prompt 里给几个标准格式的例子
3. **多次重试**：解析失败时，把错误信息告诉 LLM 让它重试
4. **正则兜底**：在极端情况下，用正则从文本里提取关键信息

**Q: 你的 Agent 如果陷入了死循环怎么办？**

A: 
1. **最大轮次限制**：Harness 里设 `max_steps=10`，到了强制结束
2. **Token 预算**：累计 token 超限时停止并输出"无法在规定步骤内完成"
3. **重复检测**：如果 Agent 连续 N 步做出相同的动作，判定为循环，中断
4. **Fallback**：上述全部失败时，直接返回已有的检索结果作为最终答案

---

## 第十一部分：文件上传 & 多模态处理

**Q: 用户上传图片或 PDF 你怎么处理？**

A: 我设计了一个 `FileParser`，根据文件扩展名分发到不同的解析器：
- 代码和文本文件直接读内容
- PDF 用 PyMuPDF 提取文字层
- 图片用 Tesseract OCR 做文字识别

提取出文本后，**后续的管道完全复用**——chunker 分块 → embedding → 存入独立的 Chroma collection。这样加一个新的文件格式只需要加一个 parser 函数，不需要改 RAG 核心代码。

**Q: 图片 OCR 不准确怎么办？**

A: 目前用的是 Tesseract 本地 OCR，准确率受图片质量影响。如果对准确率要求高的场景，可以考虑两个方向：一是上传前让用户确认 OCR 结果；二是换成多模态 LLM（如 GPT-4V）做图文理解。我这个项目里 Tesseract 够用——面试演示的场景通常是清晰的代码截图，识别率 90%+。

**Q: 上传的文件和主仓库的索引是怎么隔离和合并的？**

A: 存在两个独立的 Chroma collection。主仓库索引是 `code_index`（215 块），用户上传的代码存入 `user_upload`。Agent 搜索时通过 DenseRetriever 的 `search` 方法指定 collection_name 参数，先并查两个 collection，再合并结果做 RRF 融合和重排序。这样用户文件不会污染主仓库索引，删除用户文件时也只需要删对应的 collection。

**Q: 文件上传功能的面试价值在哪里？**

A: 
1. **展示系统可扩展性**：新文件格式只需加 parser，不碰核心 RAG 代码
2. **展示多模态处理意识**：不只处理文本，也覆盖了 PDF 和图片
3. **最佳演示效果**：面试时现场上传一段代码 → 问问题 → Agent 实时检索回答，比干讲有说服力多

---

> 最后一条建议：
> 面试官问你项目的时候，**每一个回答都要以"我"开头**——"我设计了"、"我做了消融实验"、"我发现了"。
> 不要说"这个项目实现了"——那是抄的。说"我实现了"——才是你做的。
