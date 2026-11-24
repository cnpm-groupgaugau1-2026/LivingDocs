from __future__ import annotations

from typing import Optional
from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.schemas.multimodal import OcrExtractionResponse, VisualAssetType
from app.services.ocr_engine_service import TechnicalAssetOcrEngine

router = APIRouter(prefix="/api/v1/multimodal", tags=["FE05 - Multimodal & Visual Processing"])
ocr_engine = TechnicalAssetOcrEngine()
from app.schemas.multimodal import VisualCodeConsistencyResponse
from app.services.visual_consistency_service import VisualAssetConsistencyVerifier

consistency_verifier = VisualAssetConsistencyVerifier()

@router.get("/health")
async def multimodal_health() -> dict:
    return {
        "status": "ok",
        "feature": "FE05.1 - Optical Character Recognition (OCR) Engine",
        "capabilities": ocr_engine.get_engine_capabilities(),
    }


@router.post("/ocr", response_model=OcrExtractionResponse)
async def extract_visual_asset_ocr(
    file: UploadFile = File(...),
    asset_type_hint: Optional[VisualAssetType] = Form(default=None),
) -> OcrExtractionResponse:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Thiếu tên tệp tải lên.")

    raw_bytes = await file.read()
    if not raw_bytes:
        raise HTTPException(status_code=400, detail="Tệp tải lên rỗng (0 bytes).")

    return ocr_engine.extract_from_bytes(
        file_name=file.filename,
        content_bytes=raw_bytes,
        mime_type=file.content_type or "application/octet-stream",
        asset_type_hint=asset_type_hint,
    )

from app.schemas.multimodal import VisionContextExtractionResponse
from app.services.vision_context_extractor_service import VisionContextExtractor

vision_extractor = VisionContextExtractor()


@router.post("/extract-context", response_model=VisionContextExtractionResponse)
async def extract_visual_context(
    file: UploadFile = File(...),
    context_hint: str = Form(default=""),
):
    """
    FE05.2 - Vision-LLM Context Extractor
    Phân tích sơ đồ kiến trúc, flowchart hoặc tài liệu PDF đa trang để tái dựng
    đồ thị có hướng (Nodes, Edges), luồng thực thi và các khẳng định kỹ thuật.
    """
    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Tệp tải lên rỗng.")

    return await vision_extractor.extract_context(
        file_bytes=file_bytes,
        filename=file.filename or "uploaded_asset.png",
        content_type=file.content_type or "",
        context_hint=context_hint,
    )

@router.post("/verify-consistency", response_model=VisualCodeConsistencyResponse)
async def verify_visual_code_consistency(
    file: UploadFile = File(...),
    context_hint: str = Form(default=""),
    repo_path: str = Form(default=""),
):
    """
    FE05.3 - Visual Asset - Code Consistency Verification Pipeline
    Chạy trọn vẹn FE05.1 (OCR) -> FE05.2 (Vision-LLM Graph) -> FE05.3 (AST Code Drift Verification).
    """
    raw_bytes = await file.read()
    return await consistency_verifier.verify_consistency(
        file_bytes=raw_bytes,
        filename=file.filename or "uploaded_asset.png",
        content_type=file.content_type or "",
        context_hint=context_hint,
        repo_path=repo_path,
    )