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
