from typing import List
from fastapi import APIRouter, HTTPException

from app.schemas.grounding_diff import (
    CreateGroundingSessionRequest,
    GroundingDiffSessionResponse,
    VerifyGroundingEvidenceRequest,
)
from app.services.grounding_diff_service import GroundingDiffViewerService

router = APIRouter(prefix="/api/v1/grounding-diff", tags=["grounding-diff-viewer"])
grounding_service = GroundingDiffViewerService()


@router.post("/sessions", response_model=GroundingDiffSessionResponse)
async def create_grounding_diff_session(request: CreateGroundingSessionRequest):
    """
    FE09.1 & FE09.2 - Khởi tạo phiên so sánh Side-by-Side Code-vs-Doc Diff kèm Grounding Evidence thật từ Repo.
    """
    return grounding_service.create_session(request)


@router.get("/sessions", response_model=List[GroundingDiffSessionResponse])
async def list_grounding_diff_sessions():
    return grounding_service.list_sessions()


@router.get("/sessions/{session_id}", response_model=GroundingDiffSessionResponse)
async def get_grounding_diff_session(session_id: str):
    try:
        return grounding_service.get_session(session_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/verify-evidence", response_model=GroundingDiffSessionResponse)
async def verify_grounding_evidence(request: VerifyGroundingEvidenceRequest):
    """
    FE09.2 - Reviewer xác nhận (Verify) hoặc gắn cờ (Flag) một Grounding Evidence (File Path, Line, Commit Hash).
    """
    try:
        return grounding_service.verify_evidence(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))