from fastapi import APIRouter, HTTPException

from app.services.version_audit_service import (
    ChainVerificationResult,
    CreateVersionRequest,
    DocumentAuditTrail,
    RollbackRequest,
    version_audit_service,
)

router = APIRouter(prefix="/api/v1/version-audit", tags=["fe08-version-audit"])


@router.get("/documents", response_model=list[DocumentAuditTrail])
def list_documents() -> list[DocumentAuditTrail]:
    return version_audit_service.list_documents()


@router.get("/documents/{doc_id}/history", response_model=DocumentAuditTrail)
def get_history(doc_id: str) -> DocumentAuditTrail:
    try:
        return version_audit_service.get_history(doc_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/documents/{doc_id}/versions", response_model=DocumentAuditTrail)
def append_version(doc_id: str, req: CreateVersionRequest) -> DocumentAuditTrail:
    try:
        return version_audit_service.append_version(doc_id, req)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/documents/{doc_id}/rollback", response_model=DocumentAuditTrail)
def rollback_version(doc_id: str, req: RollbackRequest) -> DocumentAuditTrail:
    try:
        return version_audit_service.rollback_version(doc_id, req)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/documents/{doc_id}/verify-chain", response_model=ChainVerificationResult)
def verify_chain(doc_id: str) -> ChainVerificationResult:
    try:
        return version_audit_service.verify_chain(doc_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc