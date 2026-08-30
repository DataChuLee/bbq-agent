import asyncio

from api.routers.knowledge import search_preview
from api.schemas import SearchPreviewRequest
from main import app


class RecordingKnowledgeService:
    def __init__(self) -> None:
        self.call: tuple[str, str, int] | None = None

    def search_preview(
        self, query: str, knowledge_type: str, top_k: int
    ) -> list[dict]:
        self.call = (query, knowledge_type, top_k)
        return [{"name": "황금올리브치킨", "score": None}]


def test_openapi_keeps_search_preview_and_removes_legacy_search() -> None:
    paths = app.openapi()["paths"]

    assert "post" in paths["/knowledge/retrieval/search-preview"]
    assert "/search" not in paths


def test_search_preview_request_and_response_contract_is_unchanged() -> None:
    service = RecordingKnowledgeService()
    body = SearchPreviewRequest(
        query="바삭한 치킨",
        knowledge_type="menu",
        top_k=3,
    )

    response = asyncio.run(search_preview(body, service))

    assert service.call == ("바삭한 치킨", "menu", 3)
    assert response.model_dump() == {
        "data": {
            "knowledge_type": "menu",
            "query": "바삭한 치킨",
            "results": [{"name": "황금올리브치킨", "score": None}],
        }
    }
