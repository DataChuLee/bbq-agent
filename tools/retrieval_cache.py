from __future__ import annotations

from functools import lru_cache
import hashlib
import json
import os
import pickle
from typing import Any

from langchain_core.documents import Document


def _stable_cache_token(value: object) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.md5(payload.encode("utf-8")).hexdigest()


class RedisRetrieverCache:
    def __init__(self, redis_client: Any, *, namespace: str, ttl: int) -> None:
        self.redis = redis_client
        self.namespace = namespace
        self.ttl = ttl
        self._hits = 0
        self._total = 0

    def _key(self, cache_key: object) -> str:
        return f"rag:{self.namespace}:{_stable_cache_token(cache_key)}"

    def get_documents(self, cache_key: object) -> list[Document] | None:
        self._total += 1
        try:
            cached = self.redis.get(self._key(cache_key))
        except Exception:
            return None

        if not cached:
            return None

        try:
            rows = pickle.loads(cached)
        except Exception:
            return None

        self._hits += 1
        return [
            Document(
                page_content=str(row.get("content", "")),
                metadata=dict(row.get("metadata") or {}),
            )
            for row in rows
            if isinstance(row, dict)
        ]

    def set_documents(self, cache_key: object, docs: list[Any]) -> None:
        rows = [
            {
                "content": getattr(doc, "page_content", ""),
                "metadata": dict(getattr(doc, "metadata", {}) or {}),
            }
            for doc in docs
        ]
        try:
            self.redis.set(self._key(cache_key), pickle.dumps(rows), ex=self.ttl)
        except Exception:
            return

    @property
    def hit_rate(self) -> float:
        return self._hits / self._total if self._total else 0.0

    def flush(self) -> int:
        try:
            keys = list(self.redis.scan_iter(f"rag:{self.namespace}:*"))
            if keys:
                self.redis.delete(*keys)
            return len(keys)
        except Exception:
            return 0


def _redis_enabled() -> bool:
    value = os.getenv("REDIS_CACHE_ENABLED", "true").strip().lower()
    return value not in {"0", "false", "no", "off"}


@lru_cache(maxsize=None)
def build_redis_cache(namespace: str, ttl: int) -> RedisRetrieverCache | None:
    if not _redis_enabled():
        return None

    try:
        import redis
    except Exception:
        return None

    host = os.getenv("REDIS_HOST", "localhost")
    port = int(os.getenv("REDIS_PORT", "6379"))
    db = int(os.getenv("REDIS_DB", "0"))
    client = redis.Redis(
        host=host,
        port=port,
        db=db,
        decode_responses=False,
        protocol=2,
    )
    return RedisRetrieverCache(client, namespace=namespace, ttl=ttl)
