from langchain_core.documents import Document

from tools.retrieval_cache import RedisRetrieverCache


class FakeRedis:
    def __init__(self) -> None:
        self.values = {}
        self.set_calls = []
        self.deleted = []

    def get(self, key: str):
        return self.values.get(key)

    def set(self, key: str, value: bytes, ex: int):
        self.set_calls.append((key, value, ex))
        self.values[key] = value

    def scan_iter(self, pattern: str):
        prefix = pattern.removesuffix("*")
        return [key for key in self.values if key.startswith(prefix)]

    def delete(self, *keys: str):
        self.deleted.extend(keys)
        for key in keys:
            self.values.pop(key, None)


class FailingRedis(FakeRedis):
    def get(self, key: str):
        raise RuntimeError("redis down")

    def set(self, key: str, value: bytes, ex: int):
        raise RuntimeError("redis down")


def test_redis_retriever_cache_round_trips_documents() -> None:
    redis_client = FakeRedis()
    cache = RedisRetrieverCache(redis_client, namespace="menu_lcel", ttl=86400)
    docs = [Document(page_content="content", metadata={"name": "menu"})]

    assert cache.get_documents({"query": "치킨"}) is None

    cache.set_documents({"query": "치킨"}, docs)
    cached_docs = cache.get_documents({"query": "치킨"})

    assert [(doc.page_content, doc.metadata) for doc in cached_docs] == [
        ("content", {"name": "menu"})
    ]
    assert redis_client.set_calls[0][2] == 86400
    assert cache.hit_rate == 0.5


def test_redis_retriever_cache_falls_back_on_redis_errors() -> None:
    cache = RedisRetrieverCache(FailingRedis(), namespace="cs_lcel", ttl=3600)

    assert cache.get_documents("배달") is None
    cache.set_documents("배달", [Document(page_content="content", metadata={})])
    assert cache.hit_rate == 0.0


def test_redis_retriever_cache_flush_uses_scan_iter_namespace() -> None:
    redis_client = FakeRedis()
    cache = RedisRetrieverCache(redis_client, namespace="menu_lcel", ttl=86400)
    cache.set_documents("a", [Document(page_content="a", metadata={})])
    cache.set_documents("b", [Document(page_content="b", metadata={})])

    assert cache.flush() == 2
    assert len(redis_client.deleted) == 2
