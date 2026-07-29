"""测试集：代码检索问题与期望结果"""

TEST_SET = [
    {
        "query": "How does TinyDB initialize and manage the default table?",
        "expected_sources": ["tinydb/database.py"],
    },
    {
        "query": "What storage backends does TinyDB support and how are they configured?",
        "expected_sources": ["tinydb/storages.py"],
    },
    {
        "query": "How does the query module implement field lookups and comparisons?",
        "expected_sources": ["tinydb/queries.py"],
    },
    {
        "query": "How are tables created, cached, and accessed in TinyDB?",
        "expected_sources": ["tinydb/table.py"],
    },
    {
        "query": "What middleware mechanisms exist for processing operations in TinyDB?",
        "expected_sources": ["tinydb/middlewares.py"],
    },
    {
        "query": "How does TinyDB handle atomic write operations in its storage layer?",
        "expected_sources": ["tinydb/storages.py"],
    },
    {
        "query": "What query operations are available for checking element membership in lists?",
        "expected_sources": ["tinydb/queries.py"],
    },
    {
        "query": "How does the Table.insert method work and what does it return?",
        "expected_sources": ["tinydb/table.py"],
    },
    {
        "query": "How does TinyDB handle JSON serialization for document storage?",
        "expected_sources": ["tinydb/storages.py", "tinydb/database.py"],
    },
    {
        "query": "What is the purpose of the Storage base class and how should it be subclassed?",
        "expected_sources": ["tinydb/storages.py"],
    },
    {
        "query": "How does TinyDB implement logical OR and AND for complex queries?",
        "expected_sources": ["tinydb/queries.py"],
    },
    {
        "query": "How does the Table class handle document IDs and the ID counter?",
        "expected_sources": ["tinydb/table.py"],
    },
    {
        "query": "How does TinyDB ensure thread safety or handle concurrent access?",
        "expected_sources": ["tinydb/database.py", "tinydb/storages.py"],
    },
    {
        "query": "How does the operations module handle updating array fields in documents?",
        "expected_sources": ["tinydb/operations.py"],
    },
    {
        "query": "How does TinyDB handle table purging and removing all documents?",
        "expected_sources": ["tinydb/table.py"],
    },
    {
        "query": "What caching strategy does the storage layer use for reading and writing data?",
        "expected_sources": ["tinydb/storages.py"],
    },
    {
        "query": "How does TinyDB implement the 'search' method to find matching documents?",
        "expected_sources": ["tinydb/table.py"],
    },
    {
        "query": "How does TinyDB's JSONStorage handle file reading and writing?",
        "expected_sources": ["tinydb/storages.py"],
    },
    {
        "query": "What happens when a document is updated using the 'update' method?",
        "expected_sources": ["tinydb/table.py"],
    },
    {
        "query": "How does the Query class implement hash-based lookup and caching?",
        "expected_sources": ["tinydb/queries.py"],
    },
]