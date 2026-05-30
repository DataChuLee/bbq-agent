import asyncio

from fastapi import APIRouter, BackgroundTasks, status

from api.dependencies import KnowledgeServiceDep
from api.exceptions import AppError
from api.schemas import DataResponse, SearchPreviewOut, SearchPreviewRequest

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


@router.get("/status")
async def get_knowledge_status(
    knowledge_svc: KnowledgeServiceDep,
) -> DataResponse[dict]:
    return DataResponse(data=knowledge_svc.get_status())


@router.get("/documents")
async def list_documents(
    knowledge_svc: KnowledgeServiceDep,
    knowledge_type: str | None = None,
) -> DataResponse[list[dict]]:
    if knowledge_type and knowledge_type not in ("menu", "cs"):
        raise AppError("INVALID_KNOWLEDGE_TYPE", "knowledge_type must be 'menu' or 'cs'")
    return DataResponse(data=knowledge_svc.list_documents(knowledge_type))


@router.post("/indexes/rebuild", status_code=status.HTTP_202_ACCEPTED)
async def rebuild_indexes(
    background_tasks: BackgroundTasks,
    knowledge_svc: KnowledgeServiceDep,
) -> DataResponse[dict]:
    # 202 반환 전에 플래그를 세워 즉각적인 status 조회에 반영되게 함
    knowledge_svc.mark_rebuilding()
    background_tasks.add_task(knowledge_svc.run_rebuild)
    return DataResponse(data={"status": "rebuilding"})


@router.post("/retrieval/search-preview")
async def search_preview(
    body: SearchPreviewRequest,
    knowledge_svc: KnowledgeServiceDep,
) -> DataResponse[SearchPreviewOut]:
    try:
        results = await asyncio.to_thread(
            knowledge_svc.search_preview,
            body.query,
            body.knowledge_type,
            body.top_k,
        )
    except Exception as exc:
        raise AppError(
            "RETRIEVAL_ERROR",
            f"Retrieval failed: {exc}",
            status_code=500,
        )
    return DataResponse(
        data=SearchPreviewOut(
            knowledge_type=body.knowledge_type,
            query=body.query,
            results=results,
        )
    )
