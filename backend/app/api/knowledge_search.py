from fastapi import APIRouter, Query

from app.services.knowledge_search_service import (
    CreateKnowledgeItemRequest,
    KnowledgeItem,
    SearchMode,
    SearchResponse,
    knowledge_search_service,
)

router = APIRouter(
    prefix="/api/v1/knowledge-search", tags=["fe12-knowledge-search"]
)


@router.get("/items", response_model=list[dict])
def list_items(collection: str = Query("ALL")) -> list[dict]:
    return knowledge_search_service.list_items(collection=collection)


@router.post("/items", response_model=KnowledgeItem)
def create_item(req: CreateKnowledgeItemRequest) -> KnowledgeItem:
    return knowledge_search_service.create_item(req)


@router.get("/search", response_model=SearchResponse)
def search_knowledge(
    q: str = Query(""),
    mode: SearchMode = Query("hybrid"),
    collection: str = Query("ALL"),
) -> SearchResponse:
    return knowledge_search_service.search(q=q, mode=mode, collection=collection)