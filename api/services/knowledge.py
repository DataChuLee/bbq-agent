import asyncio
import pickle
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

CHROMA_PATH = Path(__file__).parent.parent.parent / "vectorstore" / "chroma_db"
FAISS_PATH = Path(__file__).parent.parent.parent / "vectorstore" / "faiss_index"
BM25_PATH = Path(__file__).parent.parent.parent / "vectorstore" / "bm25_index.pkl"

_is_rebuilding: bool = False
_last_rebuilt_at: datetime | None = None


class KnowledgeService:
    def get_status(self) -> dict:
        menu_count = self._count_menu_docs()
        cs_count = self._count_cs_docs()

        if _is_rebuilding:
            index_status = "rebuilding"
        elif menu_count > 0 and cs_count > 0:
            index_status = "ready"
        else:
            index_status = "not_loaded"

        return {
            "menu_documents": menu_count,
            "cs_documents": cs_count,
            "vector_index_status": index_status,
            "last_rebuilt_at": _last_rebuilt_at.isoformat() if _last_rebuilt_at else None,
        }

    def list_documents(self, knowledge_type: str | None = None) -> list[dict]:
        docs = []
        if knowledge_type in (None, "menu"):
            docs.append({
                "type": "menu",
                "count": self._count_menu_docs(),
                "source": "chroma_db",
            })
        if knowledge_type in (None, "cs"):
            docs.append({
                "type": "cs",
                "count": self._count_cs_docs(),
                "sources": ["faiss_index", "bm25_index.pkl"],
            })
        return docs

    async def run_rebuild(self) -> None:
        global _last_rebuilt_at, _is_rebuilding
        # _is_rebuilding은 라우터에서 mark_rebuilding()으로 먼저 세운다
        try:
            await asyncio.to_thread(self._rebuild_sync)
            _last_rebuilt_at = datetime.now(timezone.utc)
        finally:
            _is_rebuilding = False

    def search_preview(
        self,
        query: str,
        knowledge_type: Literal["menu", "cs"],
        top_k: int = 5,
    ) -> list[dict]:
        if knowledge_type == "menu":
            return self._preview_menu(query, top_k)
        return self._preview_cs(query, top_k)

    # ── private helpers ────────────────────────────────────────────────────────

    def _count_menu_docs(self) -> int:
        try:
            import chromadb
            client = chromadb.PersistentClient(path=str(CHROMA_PATH))
            collection = client.get_collection("bbq_menu")
            return collection.count()
        except Exception:
            return 0

    def _count_cs_docs(self) -> int:
        try:
            with open(BM25_PATH, "rb") as f:
                bm25 = pickle.load(f)
            return len(bm25.docs)
        except Exception:
            return 0

    def mark_rebuilding(self) -> None:
        global _is_rebuilding
        _is_rebuilding = True

    def _rebuild_sync(self) -> None:
        import subprocess
        subprocess.run(
            [sys.executable, "-m", "vectorstore.build_menu_index"],
            check=True,
        )
        subprocess.run(
            [sys.executable, "-m", "vectorstore.build_cs_index"],
            check=True,
        )
        # 재빌드 완료 후 캐시 무효화해 다음 호출 시 새 인덱스를 로드하게 함
        from tools.search_menu import _get_retriever as _menu_r
        from tools.search_cs import _get_retriever as _cs_r
        _menu_r.cache_clear()
        _cs_r.cache_clear()

    def _preview_menu(self, query: str, top_k: int) -> list[dict]:
        from tools.search_menu import _get_retriever
        # vectorstore를 직접 호출해 singleton의 search_kwargs를 변조하지 않음
        vectorstore = _get_retriever().vectorstore
        docs = vectorstore.similarity_search(query, k=top_k)
        return [{"content": d.page_content, "metadata": d.metadata} for d in docs]

    def _preview_cs(self, query: str, top_k: int) -> list[dict]:
        from tools.search_cs import _get_retriever
        retriever = _get_retriever()
        docs = retriever.invoke(query)
        return [
            {"content": d.page_content, "metadata": d.metadata}
            for d in docs[:top_k]
        ]
