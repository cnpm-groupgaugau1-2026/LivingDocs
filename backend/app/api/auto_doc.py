from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Body, Header, HTTPException

from app.schemas.auto_doc import (
    AcceptDraftRequest,
    AutoDocWorkflowResponse,
    CodeChangeEventRequest,
    EditDraftRequest,
    RegenerateDraftRequest,
    RollbackVersionRequest,
)
from app.services.auto_doc_service import AutomaticDocUpdateService

router = APIRouter(prefix="/api/v1/auto-doc", tags=["auto-doc-update"])
auto_doc_service = AutomaticDocUpdateService()


@router.post("/trigger", response_model=AutoDocWorkflowResponse)
async def trigger_auto_doc_workflow(request: CodeChangeEventRequest):
    """
    FE03.1 - Kích hoạt quy trình tự động cập nhật tài liệu từ sự kiện PR hoặc Commit.
    """
    return await auto_doc_service.trigger_update_workflow(request)


@router.post("/github-webhook", response_model=AutoDocWorkflowResponse)
async def receive_github_webhook(
    payload: Dict[str, Any] = Body(...),
    x_github_event: Optional[str] = Header(default="push"),
):
    """
    FE03.1 - Endpoint nhận sự kiện Webhook trực tiếp từ GitHub (push / pull_request).
    """
    return await auto_doc_service.handle_github_webhook(
        github_event=x_github_event or "push",
        payload=payload,
    )


@router.get("/workflows", response_model=List[AutoDocWorkflowResponse])
async def list_auto_doc_workflows():
    """
    FE03.2 - Lấy danh sách các phiên làm việc tự động cập nhật tài liệu và bảng so sánh Side-by-Side.
    """
    return auto_doc_service.list_workflows()


@router.get("/workflows/{workflow_id}", response_model=AutoDocWorkflowResponse)
async def get_auto_doc_workflow(workflow_id: str):
    try:
        return auto_doc_service.get_workflow(workflow_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/actions/accept", response_model=AutoDocWorkflowResponse)
async def accept_documentation_draft(request: AcceptDraftRequest):
    """
    FE03.3 - Phê duyệt (Accept) bản nháp tài liệu thành phiên bản chính thức (Published).
    """
    try:
        return auto_doc_service.accept_draft(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/actions/edit", response_model=AutoDocWorkflowResponse)
async def edit_documentation_draft(request: EditDraftRequest):
    """
    FE03.3 - Chỉnh sửa thủ công (Edit) nội dung bản nháp và tính lại bảng diff song song.
    """
    try:
        return auto_doc_service.edit_draft(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/actions/regenerate", response_model=AutoDocWorkflowResponse)
async def regenerate_documentation_draft(request: RegenerateDraftRequest):
    """
    FE03.3 - Yêu cầu AI sinh lại (Regenerate) bản nháp với chỉ dẫn tùy chỉnh.
    """
    try:
        return await auto_doc_service.regenerate_draft(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/actions/rollback", response_model=AutoDocWorkflowResponse)
async def rollback_documentation_version(request: RollbackVersionRequest):
    """
    FE03.3 - Khôi phục (Rollback) tài liệu về một phiên bản ổn định trước đó.
    """
    try:
        return auto_doc_service.rollback_version(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))