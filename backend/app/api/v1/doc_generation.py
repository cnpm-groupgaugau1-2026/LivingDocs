import base64
import os
import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.rbac import RequireRole, get_current_user
from app.models.user import Role, User
from app.schemas.ast_doc import (
    ASTParseRequest,
    ASTParseResponse,
    CoverageReport,
    DraftGenerationRequest,
    DraftGenerationResponse,
)
from app.services.ai_doc_generator_service import ai_doc_generator_service
from app.services.ast_parser_service import ast_parser_service
from app.services.coverage_analyzer_service import coverage_analyzer_service

router = APIRouter(
    prefix="/api/v1/doc-generation",
    tags=["FE02 - AST AI Documentation"],
    dependencies=[
        Depends(
            RequireRole(
                [
                    Role.DEVELOPER,
                    Role.STAFF,
                    Role.MANAGER,
                    Role.TECH_LEAD,
                    Role.ADMINISTRATOR,
                ]
            )
        )
    ],
)

SUPPORTED_EXTENSIONS = {".py", ".js", ".jsx", ".ts", ".tsx"}
IGNORED_DIRS = ("node_modules/", "venv/", ".venv/", "__pycache__/", ".next/", "dist/", "build/")


@router.get("/repo-code-files")
async def list_repo_code_files(
    repo_name: str,
    current_user: User = Depends(get_current_user),
):
    """Lấy danh sách tệp mã nguồn hỗ trợ AST (.py, .js, .ts, .tsx) từ GitHub Workspace."""
    if not current_user.github_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tài khoản chưa liên kết GitHub OAuth.",
        )

    repo_clean = repo_name.strip().strip("/")
    headers = {
        "Authorization": f"Bearer {current_user.github_token}",
        "Accept": "application/vnd.github+json",
    }

    async with httpx.AsyncClient(timeout=20.0) as client:
        repo_res = await client.get(f"https://api.github.com/repos/{repo_clean}", headers=headers)
        if repo_res.status_code != 200:
            raise HTTPException(
                status_code=repo_res.status_code,
                detail=f"Không thể truy cập repository '{repo_clean}'.",
            )
        default_branch = repo_res.json().get("default_branch", "main")

        tree_res = await client.get(
            f"https://api.github.com/repos/{repo_clean}/git/trees/{default_branch}?recursive=1",
            headers=headers,
        )
        if tree_res.status_code != 200:
            return {"repo_name": repo_clean, "branch": default_branch, "files": []}

        files = []
        for item in tree_res.json().get("tree", []):
            if item.get("type") != "blob":
                continue
            path = item.get("path", "")
            if any(path.startswith(ignored) or f"/{ignored}" in path for ignored in IGNORED_DIRS):
                continue
            _, ext = os.path.splitext(path.lower())
            if ext in SUPPORTED_EXTENSIONS:
                files.append(
                    {
                        "path": path,
                        "sha": item.get("sha"),
                        "language": ast_parser_service.EXTENSION_MAP.get(ext, "unknown"),
                    }
                )

    return {
        "repo_name": repo_clean,
        "branch": default_branch,
        "total_files": len(files),
        "files": files[:100],
    }


@router.get("/repo-file-content")
async def get_repo_file_content(
    repo_name: str,
    file_path: str,
    current_user: User = Depends(get_current_user),
):
    """Đọc nội dung mã nguồn của 1 tệp cụ thể từ GitHub Workspace."""
    if not current_user.github_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tài khoản chưa liên kết GitHub OAuth.",
        )

    repo_clean = repo_name.strip().strip("/")
    path_clean = file_path.strip().lstrip("/")
    headers = {
        "Authorization": f"Bearer {current_user.github_token}",
        "Accept": "application/vnd.github+json",
    }

    async with httpx.AsyncClient(timeout=20.0) as client:
        res = await client.get(
            f"https://api.github.com/repos/{repo_clean}/contents/{path_clean}",
            headers=headers,
        )
        if res.status_code != 200:
            raise HTTPException(
                status_code=res.status_code,
                detail=f"Không đọc được tệp '{path_clean}' từ GitHub.",
            )
        data = res.json()
        raw_b64 = data.get("content", "")
        source_code = base64.b64decode(raw_b64).decode("utf-8", errors="replace")

    _, ext = os.path.splitext(path_clean.lower())
    return {
        "repo_name": repo_clean,
        "file_path": path_clean,
        "language": ast_parser_service.EXTENSION_MAP.get(ext, "python"),
        "source_code": source_code,
    }


@router.post("/parse", response_model=ASTParseResponse)
def parse_source_code_ast(
    payload: ASTParseRequest,
    current_user: User = Depends(get_current_user),
):
    """4.1: Phân tích mã nguồn đa ngôn ngữ (Python, JS, TS) sang cây AST."""
    try:
        return ast_parser_service.parse_code(
            file_path=payload.file_path,
            source_code=payload.source_code,
            language=payload.language,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("/analyze-gaps", response_model=CoverageReport)
def analyze_documentation_coverage(
    payload: ASTParseRequest,
    current_user: User = Depends(get_current_user),
):
    """4.2: Tính điểm độ phủ tài liệu và phát hiện các thực thể thiếu docstring/type hint."""
    try:
        return coverage_analyzer_service.analyze_from_code(
            file_path=payload.file_path,
            source_code=payload.source_code,
            language=payload.language,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("/generate-draft", response_model=DraftGenerationResponse)
async def generate_ai_documentation_draft(
    payload: DraftGenerationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """4.3: Pipeline sinh bản nháp tài liệu Markdown từ AST + Template (FE11) + AI Config (FE13)."""
    try:
        return await ai_doc_generator_service.generate_draft(payload=payload, db=db)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))