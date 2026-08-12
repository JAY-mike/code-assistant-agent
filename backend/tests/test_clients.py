"""Shared process-client tests without Redis or Chroma services."""


def test_redis_client_is_initialized_once(monkeypatch):
    from app import clients

    created = []

    class FakeRedis:
        def ping(self):
            return True

    def create_redis(**kwargs):
        created.append(kwargs)
        return FakeRedis()

    clients._redis_client = None
    clients._redis_initialized = False
    monkeypatch.setattr(clients.redis_lib, "Redis", create_redis)
    try:
        first = clients.get_redis_client()
        second = clients.get_redis_client()

        assert first is second
        assert len(created) == 1
    finally:
        clients._redis_client = None
        clients._redis_initialized = False


def test_chroma_client_is_reused_for_the_same_persist_directory(monkeypatch, tmp_path):
    from app.rag import dense_retriever

    created = []

    class FakePersistentClient:
        def __init__(self, path):
            created.append(path)

    dense_retriever._chroma_clients.clear()
    monkeypatch.setattr(dense_retriever.chromadb, "PersistentClient", FakePersistentClient)
    try:
        first = dense_retriever.get_chroma_client(str(tmp_path))
        second = dense_retriever.get_chroma_client(str(tmp_path))

        assert first is second
        assert len(created) == 1
    finally:
        dense_retriever._chroma_clients.clear()
