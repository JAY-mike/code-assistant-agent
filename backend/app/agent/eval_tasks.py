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
