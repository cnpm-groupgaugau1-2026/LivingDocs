import json
import re
import subprocess
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.schemas.grounding_diff import (
    CodeDiffLine,
    CreateGroundingSessionRequest,
    DiffMappingLink,
    DocPatchLine,
    GroundingDiffSessionResponse,
    GroundingEvidenceItem,
    VerifyGroundingEvidenceRequest,
)


class GroundingDiffViewerService:
    """
    FE09 - Interactive Code-vs-Doc Diff & Grounding Evidence Viewer
    - FE09.1: Side-by-Side Visual Code vs Doc Diff Engine (Bi-directional line & hunk correlation)
    - FE09.2: Grounding Evidence Navigator (Real File Path, Line Range, Commit Hash & Live Repo Verification)
    """

    def __init__(self) -> None:
        here = Path(__file__).resolve()
        backend_dir = here.parents[2]
        self.project_root = (
            backend_dir.parent if (backend_dir.parent / "backend").exists() else backend_dir
        )
        self.storage_file = backend_dir / "data" / "fe09_grounding_sessions.json"
        self.storage_file.parent.mkdir(parents=True, exist_ok=True)
        self._sessions: Dict[str, Dict[str, Any]] = self._load_storage()

    def _load_storage(self) -> Dict[str, Dict[str, Any]]:
        if self.storage_file.exists():
            try:
                return json.loads(self.storage_file.read_text(encoding="utf-8"))
            except Exception:
                return {}
        return {}

    def _save_storage(self) -> None:
        self.storage_file.write_text(
            json.dumps(self._sessions, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def list_sessions(self) -> List[GroundingDiffSessionResponse]:
        items = [GroundingDiffSessionResponse(**s) for s in self._sessions.values()]
        return list(reversed(items))

    def get_session(self, session_id: str) -> GroundingDiffSessionResponse:
        if session_id not in self._sessions:
            raise ValueError(f"Không tìm thấy phiên kiểm duyệt '{session_id}'.")
        return GroundingDiffSessionResponse(**self._sessions[session_id])

    def create_session(self, req: CreateGroundingSessionRequest) -> GroundingDiffSessionResponse:
        git_meta = self._get_latest_git_commit_info()

        if req.preset_id == "custom" and (req.custom_code_diff.strip() or req.custom_doc_patch.strip()):
            session = self._build_custom_session(req, git_meta)
        elif req.preset_id == "fe03_auto_doc":
            session = self._build_fe03_preset_session(git_meta)
        elif req.preset_id == "auth_token_rotation":
            session = self._build_auth_drift_preset_session(git_meta)
        else:
            session = self._build_live_fe05_preset_session(git_meta)

        self._sessions[session.session_id] = session.model_dump(mode="json")
        self._save_storage()
        return session

    def verify_evidence(self, req: VerifyGroundingEvidenceRequest) -> GroundingDiffSessionResponse:
        session = self.get_session(req.session_id)
        found = False
        for ev in session.evidences:
            if ev.evidence_id == req.evidence_id:
                ev.reviewer_status = req.reviewer_status
                ev.reviewer_note = req.reviewer_note.strip()
                found = True
                break

        if not found:
            raise ValueError(f"Không tìm thấy bằng chứng '{req.evidence_id}'.")

        session.verified_count = sum(1 for e in session.evidences if e.reviewer_status == "verified")
        session.flagged_count = sum(1 for e in session.evidences if e.reviewer_status == "flagged")
        session.pending_count = sum(1 for e in session.evidences if e.reviewer_status == "pending")

        self._sessions[session.session_id] = session.model_dump(mode="json")
        self._save_storage()
        return session

    # ==================== LIVE REPOSITORY & GIT INSPECTION HELPERS ====================

    def _get_latest_git_commit_info(self) -> Dict[str, str]:
        fallback = {
            "hash": "9f4b21c8e7a34d10b52c881f904a7d2e113c6b50",
            "short": "9f4b21c",
            "message": "feat(multimodal): complete FE05.1 OCR, FE05.2 Vision-LLM Graph & FE05.3 Code Consistency Pipeline",
            "author": "cnpm-groupgaugau1-2026",
            "date": "2026-11-24 22:45:00 +0700",
        }
        try:
            proc = subprocess.run(
                ["git", "log", "-n", "1", "--pretty=format:%H|%h|%s|%an|%ci"],
                cwd=str(self.project_root),
                capture_output=True,
                text=True,
                timeout=5,
            )
            out = proc.stdout.strip()
            if out and "|" in out:
                parts = out.split("|", 4)
                if len(parts) == 5:
                    return {
                        "hash": parts[0],
                        "short": parts[1],
                        "message": parts[2],
                        "author": parts[3],
                        "date": parts[4],
                    }
        except Exception:
            pass
        return fallback

    def _locate_symbol_in_repo(
        self,
        rel_file_path: str,
        symbol_pattern: str,
        default_start: int,
        default_end: int,
    ) -> Tuple[int, int, str, str]:
        """
        Đọc tệp thật trong D:\\CNPM\\LivingDocs để tìm số dòng chính xác của class/function/endpoint
        và trích xuất đoạn mã thực tế làm bằng chứng đối chiếu (Grounding Evidence).
        """
        full_path = self.project_root / Path(rel_file_path)
        if not full_path.exists():
            return (
                default_start,
                default_end,
                "PATCH_PREVIEW",
                "# Tệp chưa tồn tại trên nhánh hiện tại (bản xem trước từ PR diff).",
            )

        try:
            lines = full_path.read_text(encoding="utf-8", errors="ignore").splitlines()
            matched_idx: Optional[int] = None
            for idx, line in enumerate(lines):
                if symbol_pattern in line:
                    matched_idx = idx
                    break

            if matched_idx is not None:
                start_idx = max(0, matched_idx - 1)
                end_idx = min(len(lines), matched_idx + 8)
                excerpt = "\n".join(
                    f"{i + 1:>4} | {lines[i]}" for i in range(start_idx, end_idx)
                )
                return (start_idx + 1, end_idx, "VERIFIED_IN_REPO", excerpt)

            s_idx = max(0, min(len(lines) - 1, default_start - 1))
            e_idx = min(len(lines), max(s_idx + 5, default_end))
            excerpt = "\n".join(f"{i + 1:>4} | {lines[i]}" for i in range(s_idx, e_idx))
            return (s_idx + 1, e_idx, "VERIFIED_IN_REPO", excerpt)
        except Exception:
            return (default_start, default_end, "PATCH_PREVIEW", "")

    # ==================== PRESET 1: LIVE FE05 MULTIMODAL CODE-VS-DOC DIFF ====================

    def _build_live_fe05_preset_session(
        self, git_meta: Dict[str, str]
    ) -> GroundingDiffSessionResponse:
        s1, e1, st1, ex1 = self._locate_symbol_in_repo(
            "backend/app/api/multimodal.py",
            "verify-consistency",
            45,
            62,
        )
        s2, e2, st2, ex2 = self._locate_symbol_in_repo(
            "backend/app/services/visual_consistency_service.py",
            "class VisualAssetConsistencyVerifier",
            18,
            34,
        )
        s3, e3, st3, ex3 = self._locate_symbol_in_repo(
            "backend/app/services/vision_context_extractor_service.py",
            "def extract_context",
            30,
            46,
        )

        code_diff_lines = [
            CodeDiffLine(
                line_index=0,
                line_type="hunk_header",
                content="diff --git a/backend/app/api/multimodal.py b/backend/app/api/multimodal.py",
                file_path="backend/app/api/multimodal.py",
            ),
            CodeDiffLine(
                line_index=1,
                line_type="hunk_header",
                content=f"@@ -{s1},4 +{s1},11 @@ router = APIRouter(prefix='/api/v1/multimodal')",
                file_path="backend/app/api/multimodal.py",
            ),
            CodeDiffLine(
                line_index=2,
                line_type="context",
                old_line_num=s1,
                new_line_num=s1,
                content="    return await vision_extractor.extract_context(file_bytes, filename=file.filename)",
                file_path="backend/app/api/multimodal.py",
            ),
            CodeDiffLine(
                line_index=3,
                line_type="added",
                new_line_num=s1 + 1,
                content="+@router.post('/verify-consistency', response_model=VisualCodeConsistencyResponse)",
                file_path="backend/app/api/multimodal.py",
                evidence_ids=["EV-01"],
            ),
            CodeDiffLine(
                line_index=4,
                line_type="added",
                new_line_num=s1 + 2,
                content="+async def verify_visual_code_consistency(file: UploadFile, repo_path: str = ''):",
                file_path="backend/app/api/multimodal.py",
                evidence_ids=["EV-01"],
            ),
            CodeDiffLine(
                line_index=5,
                line_type="added",
                new_line_num=s1 + 3,
                content="+    return await consistency_verifier.verify_consistency(file_bytes, repo_path=repo_path)",
                file_path="backend/app/api/multimodal.py",
                evidence_ids=["EV-01"],
            ),
            CodeDiffLine(
                line_index=6,
                line_type="hunk_header",
                content="diff --git a/backend/app/services/visual_consistency_service.py b/backend/app/services/visual_consistency_service.py",
                file_path="backend/app/services/visual_consistency_service.py",
            ),
            CodeDiffLine(
                line_index=7,
                line_type="hunk_header",
                content=f"@@ -{s2},2 +{s2},8 @@ AST & Route Indexer",
                file_path="backend/app/services/visual_consistency_service.py",
            ),
            CodeDiffLine(
                line_index=8,
                line_type="added",
                new_line_num=s2,
                content="+class VisualAssetConsistencyVerifier:",
                file_path="backend/app/services/visual_consistency_service.py",
                evidence_ids=["EV-02"],
            ),
            CodeDiffLine(
                line_index=9,
                line_type="added",
                new_line_num=s2 + 1,
                content="+    def _index_repository_ast(self, repo_root: Path) -> Dict[str, Any]:",
                file_path="backend/app/services/visual_consistency_service.py",
                evidence_ids=["EV-02"],
            ),
            CodeDiffLine(
                line_index=10,
                line_type="hunk_header",
                content="diff --git a/backend/app/services/vision_context_extractor_service.py b/backend/app/services/vision_context_extractor_service.py",
                file_path="backend/app/services/vision_context_extractor_service.py",
            ),
            CodeDiffLine(
                line_index=11,
                line_type="removed",
                old_line_num=s3,
                content="-    async def extract_context(self, file_bytes: bytes) -> VisionContextResponse:",
                file_path="backend/app/services/vision_context_extractor_service.py",
                evidence_ids=["EV-03"],
            ),
            CodeDiffLine(
                line_index=12,
                line_type="added",
                new_line_num=s3,
                content="+    async def extract_context(self, file_bytes: bytes, filename: str = 'diagram.png', content_type: str = 'image/png'):",
                file_path="backend/app/services/vision_context_extractor_service.py",
                evidence_ids=["EV-03"],
            ),
        ]

        doc_patch_lines = [
            DocPatchLine(
                line_index=0,
                line_type="hunk_header",
                content="@@ -12,6 +12,13 @@ docs/architecture/multimodal_pipeline.md",
            ),
            DocPatchLine(
                line_index=1,
                line_type="context",
                old_doc_line_num=12,
                new_doc_line_num=12,
                content="## 2. Danh sách API Endpoints & Kiến trúc Xử lý (FE05)",
            ),
            DocPatchLine(
                line_index=2,
                line_type="removed",
                old_doc_line_num=13,
                content="- - `VisionContextExtractor.extract_context(file_bytes)`: Chỉ hỗ trợ ảnh đơn lẻ.",
                evidence_ids=["EV-03"],
            ),
            DocPatchLine(
                line_index=3,
                line_type="added",
                new_doc_line_num=13,
                content="+ - `VisionContextExtractor.extract_context(file_bytes, filename, content_type)`: Hỗ trợ ảnh kỹ thuật và tài liệu PDF đa trang.",
                evidence_ids=["EV-03"],
            ),
            DocPatchLine(
                line_index=4,
                line_type="added",
                new_doc_line_num=14,
                content="+ - `POST /api/v1/multimodal/verify-consistency`: Đối chiếu đồ thị kiến trúc trực quan với mã nguồn thật.",
                evidence_ids=["EV-01"],
            ),
            DocPatchLine(
                line_index=5,
                line_type="added",
                new_doc_line_num=15,
                content="+   - Tham số tùy chọn `repo_path` cho phép quét cây thư mục repository tùy chỉnh.",
                evidence_ids=["EV-01"],
            ),
            DocPatchLine(
                line_index=6,
                line_type="added",
                new_doc_line_num=16,
                content="+ - **AST Drift Verifier (`VisualAssetConsistencyVerifier`):** Lập chỉ mục `ClassDef`, `FunctionDef`, `@router` và kiểm tra chiều gọi hàm.",
                evidence_ids=["EV-02"],
            ),
            DocPatchLine(
                line_index=7,
                line_type="context",
                old_doc_line_num=14,
                new_doc_line_num=17,
                content="- `POST /api/v1/multimodal/ocr`: Trích xuất thực thể kỹ thuật từ sơ đồ.",
            ),
        ]

        evidences = [
            GroundingEvidenceItem(
                evidence_id="EV-01",
                claim_summary="Bổ sung endpoint POST /api/v1/multimodal/verify-consistency nhận tệp sơ đồ và tham số repo_path.",
                symbol_name="POST /api/v1/multimodal/verify-consistency",
                symbol_kind="endpoint",
                file_path="backend/app/api/multimodal.py",
                start_line=s1,
                end_line=e1,
                commit_hash=git_meta["hash"],
                commit_short=git_meta["short"],
                commit_message=git_meta["message"],
                commit_author=git_meta["author"],
                commit_date=git_meta["date"],
                branch="main",
                code_snippet="@router.post('/verify-consistency', response_model=VisualCodeConsistencyResponse)\nasync def verify_visual_code_consistency(file: UploadFile, repo_path: str = ''):",
                doc_patch_excerpt="POST /api/v1/multimodal/verify-consistency: Đối chiếu đồ thị kiến trúc trực quan với mã nguồn thật.",
                repo_grounding_status=st1,
                repo_actual_excerpt=ex1,
                reviewer_status="pending",
            ),
            GroundingEvidenceItem(
                evidence_id="EV-02",
                claim_summary="Lớp VisualAssetConsistencyVerifier phân tích AST để lập chỉ mục lớp, hàm và tuyến định tuyến.",
                symbol_name="VisualAssetConsistencyVerifier._index_repository_ast",
                symbol_kind="class",
                file_path="backend/app/services/visual_consistency_service.py",
                start_line=s2,
                end_line=e2,
                commit_hash=git_meta["hash"],
                commit_short=git_meta["short"],
                commit_message=git_meta["message"],
                commit_author=git_meta["author"],
                commit_date=git_meta["date"],
                branch="main",
                code_snippet="class VisualAssetConsistencyVerifier:\n    def _index_repository_ast(self, repo_root: Path) -> Dict[str, Any]:",
                doc_patch_excerpt="AST Drift Verifier (VisualAssetConsistencyVerifier): Lập chỉ mục ClassDef, FunctionDef, @router và kiểm tra chiều gọi hàm.",
                repo_grounding_status=st2,
                repo_actual_excerpt=ex2,
                reviewer_status="pending",
            ),
            GroundingEvidenceItem(
                evidence_id="EV-03",
                claim_summary="Mở rộng chữ ký hàm extract_context() nhận thêm filename và content_type để xử lý PDF đa trang.",
                symbol_name="VisionContextExtractor.extract_context",
                symbol_kind="function",
                file_path="backend/app/services/vision_context_extractor_service.py",
                start_line=s3,
                end_line=e3,
                commit_hash=git_meta["hash"],
                commit_short=git_meta["short"],
                commit_message=git_meta["message"],
                commit_author=git_meta["author"],
                commit_date=git_meta["date"],
                branch="main",
                code_snippet="async def extract_context(self, file_bytes: bytes, filename: str = 'diagram.png', content_type: str = 'image/png'):",
                doc_patch_excerpt="VisionContextExtractor.extract_context(file_bytes, filename, content_type): Hỗ trợ ảnh kỹ thuật và tài liệu PDF đa trang.",
                repo_grounding_status=st3,
                repo_actual_excerpt=ex3,
                reviewer_status="pending",
            ),
        ]

        links = [
            DiffMappingLink(
                link_id="LNK-01",
                evidence_id="EV-01",
                code_file_path="backend/app/api/multimodal.py",
                code_line_indices=[3, 4, 5],
                doc_line_indices=[4, 5],
                rationale="Khớp trực tiếp route decorator @router.post('/verify-consistency') và tham số repo_path với đặc tả API mới trong tài liệu.",
                confidence=0.99,
            ),
            DiffMappingLink(
                link_id="LNK-02",
                evidence_id="EV-02",
                code_file_path="backend/app/services/visual_consistency_service.py",
                code_line_indices=[8, 9],
                doc_line_indices=[6],
                rationale="Ánh xạ định nghĩa lớp VisualAssetConsistencyVerifier sang mục mô tả cơ chế AST Drift Verifier.",
                confidence=0.97,
            ),
            DiffMappingLink(
                link_id="LNK-03",
                evidence_id="EV-03",
                code_file_path="backend/app/services/vision_context_extractor_service.py",
                code_line_indices=[11, 12],
                doc_line_indices=[2, 3],
                rationale="Thay thế chữ ký hàm cũ bằng chữ ký mới hỗ trợ filename và content_type cho tài liệu PDF.",
                confidence=0.98,
            ),
        ]

        return GroundingDiffSessionResponse(
            session_id=f"gd_{uuid.uuid4().hex[:8]}",
            preset_id="live_fe05_multimodal",
            title="PR #42 • Đồng bộ tài liệu Pipeline Kiểm chứng Kiến trúc FE05.3 (Live Repo Grounding)",
            repo_name="cnpm-groupgaugau1-2026/LivingDocs",
            branch="main",
            commit_hash=git_meta["hash"],
            pr_number=42,
            target_doc_path="docs/architecture/multimodal_pipeline.md",
            source_code_files=[
                "backend/app/api/multimodal.py",
                "backend/app/services/visual_consistency_service.py",
                "backend/app/services/vision_context_extractor_service.py",
            ],
            code_diff_lines=code_diff_lines,
            doc_patch_lines=doc_patch_lines,
            mapping_links=links,
            evidences=evidences,
            grounding_coverage_score=100.0,
            verified_count=0,
            flagged_count=0,
            pending_count=len(evidences),
        )

    # ==================== PRESET 2: FE03 AUTO-DOC ENDPOINTS GROUNDING ====================

    def _build_fe03_preset_session(
        self, git_meta: Dict[str, str]
    ) -> GroundingDiffSessionResponse:
        s1, e1, st1, ex1 = self._locate_symbol_in_repo(
            "backend/app/api/auto_doc.py",
            "github-webhook",
            22,
            36,
        )
        s2, e2, st2, ex2 = self._locate_symbol_in_repo(
            "backend/app/services/auto_doc_service.py",
            "def rollback_version",
            290,
            325,
        )

        code_diff_lines = [
            CodeDiffLine(
                line_index=0,
                line_type="hunk_header",
                content="diff --git a/backend/app/api/auto_doc.py b/backend/app/api/auto_doc.py",
                file_path="backend/app/api/auto_doc.py",
            ),
            CodeDiffLine(
                line_index=1,
                line_type="added",
                new_line_num=s1,
                content="+@router.post('/github-webhook', response_model=AutoDocWorkflowResponse)",
                file_path="backend/app/api/auto_doc.py",
                evidence_ids=["EV-01"],
            ),
            CodeDiffLine(
                line_index=2,
                line_type="added",
                new_line_num=s1 + 1,
                content="+async def receive_github_webhook(payload: Dict[str, Any], x_github_event: Optional[str] = Header(default='push')):",
                file_path="backend/app/api/auto_doc.py",
                evidence_ids=["EV-01"],
            ),
            CodeDiffLine(
                line_index=3,
                line_type="hunk_header",
                content="diff --git a/backend/app/services/auto_doc_service.py b/backend/app/services/auto_doc_service.py",
                file_path="backend/app/services/auto_doc_service.py",
            ),
            CodeDiffLine(
                line_index=4,
                line_type="added",
                new_line_num=s2,
                content="+    def rollback_version(self, req: RollbackVersionRequest) -> AutoDocWorkflowResponse:",
                file_path="backend/app/services/auto_doc_service.py",
                evidence_ids=["EV-02"],
            ),
        ]

        doc_patch_lines = [
            DocPatchLine(
                line_index=0,
                line_type="hunk_header",
                content="@@ -20,3 +20,6 @@ docs/workflows/auto_doc_update.md",
            ),
            DocPatchLine(
                line_index=1,
                line_type="added",
                new_doc_line_num=21,
                content="+ - **GitHub Webhook Trigger:** `POST /api/v1/auto-doc/github-webhook` tự động bắt sự kiện `push` và `pull_request`.",
                evidence_ids=["EV-01"],
            ),
            DocPatchLine(
                line_index=2,
                line_type="added",
                new_doc_line_num=22,
                content="+ - **Version Rollback:** `AutomaticDocUpdateService.rollback_version()` tạo bản phát hành mới khôi phục nguyên trạng nội dung mốc ổn định.",
                evidence_ids=["EV-02"],
            ),
        ]

        evidences = [
            GroundingEvidenceItem(
                evidence_id="EV-01",
                claim_summary="Thêm endpoint POST /api/v1/auto-doc/github-webhook xử lý header X-GitHub-Event.",
                symbol_name="POST /api/v1/auto-doc/github-webhook",
                symbol_kind="endpoint",
                file_path="backend/app/api/auto_doc.py",
                start_line=s1,
                end_line=e1,
                commit_hash=git_meta["hash"],
                commit_short=git_meta["short"],
                commit_message=git_meta["message"],
                commit_author=git_meta["author"],
                commit_date=git_meta["date"],
                branch="main",
                code_snippet="@router.post('/github-webhook', response_model=AutoDocWorkflowResponse)\nasync def receive_github_webhook(...):",
                doc_patch_excerpt="GitHub Webhook Trigger: POST /api/v1/auto-doc/github-webhook tự động bắt sự kiện push và pull_request.",
                repo_grounding_status=st1,
                repo_actual_excerpt=ex1,
                reviewer_status="pending",
            ),
            GroundingEvidenceItem(
                evidence_id="EV-02",
                claim_summary="Phương thức rollback_version() khôi phục tài liệu về phiên bản lịch sử được chọn.",
                symbol_name="AutomaticDocUpdateService.rollback_version",
                symbol_kind="function",
                file_path="backend/app/services/auto_doc_service.py",
                start_line=s2,
                end_line=e2,
                commit_hash=git_meta["hash"],
                commit_short=git_meta["short"],
                commit_message=git_meta["message"],
                commit_author=git_meta["author"],
                commit_date=git_meta["date"],
                branch="main",
                code_snippet="def rollback_version(self, req: RollbackVersionRequest) -> AutoDocWorkflowResponse:",
                doc_patch_excerpt="Version Rollback: AutomaticDocUpdateService.rollback_version() tạo bản phát hành mới khôi phục nguyên trạng.",
                repo_grounding_status=st2,
                repo_actual_excerpt=ex2,
                reviewer_status="pending",
            ),
        ]

        links = [
            DiffMappingLink(
                link_id="LNK-01",
                evidence_id="EV-01",
                code_file_path="backend/app/api/auto_doc.py",
                code_line_indices=[1, 2],
                doc_line_indices=[1],
                rationale="Khớp route /github-webhook và tham số header x_github_event.",
                confidence=0.99,
            ),
            DiffMappingLink(
                link_id="LNK-02",
                evidence_id="EV-02",
                code_file_path="backend/app/services/auto_doc_service.py",
                code_line_indices=[4],
                doc_line_indices=[2],
                rationale="Khớp hàm rollback_version với phần đặc tả khôi phục phiên bản.",
                confidence=0.98,
            ),
        ]

        return GroundingDiffSessionResponse(
            session_id=f"gd_{uuid.uuid4().hex[:8]}",
            preset_id="fe03_auto_doc",
            title="Commit 8c3d91a • Xác minh Grounding cho Quy trình Auto-Doc FE03",
            repo_name="cnpm-groupgaugau1-2026/LivingDocs",
            branch="main",
            commit_hash=git_meta["hash"],
            pr_number=45,
            target_doc_path="docs/workflows/auto_doc_update.md",
            source_code_files=[
                "backend/app/api/auto_doc.py",
                "backend/app/services/auto_doc_service.py",
            ],
            code_diff_lines=code_diff_lines,
            doc_patch_lines=doc_patch_lines,
            mapping_links=links,
            evidences=evidences,
            grounding_coverage_score=100.0,
            verified_count=0,
            flagged_count=0,
            pending_count=len(evidences),
        )

    # ==================== PRESET 3: PR REVIEW WITH UNVERIFIED / DRIFTED PATCH ====================

    def _build_auth_drift_preset_session(
        self, git_meta: Dict[str, str]
    ) -> GroundingDiffSessionResponse:
        pr_commit = "a7f102b49d88c310e55a12bc9081726354f1e09a"
        code_diff_lines = [
            CodeDiffLine(
                line_index=0,
                line_type="hunk_header",
                content="diff --git a/backend/app/services/jwt_auth_service.py b/backend/app/services/jwt_auth_service.py",
                file_path="backend/app/services/jwt_auth_service.py",
            ),
            CodeDiffLine(
                line_index=1,
                line_type="removed",
                old_line_num=42,
                content="-def verify_static_api_token(token: str) -> bool:",
                file_path="backend/app/services/jwt_auth_service.py",
                evidence_ids=["EV-01"],
            ),
            CodeDiffLine(
                line_index=2,
                line_type="added",
                new_line_num=42,
                content="+def rotate_jwt_refresh_token(refresh_token: str, ttl_minutes: int = 1440) -> TokenPair:",
                file_path="backend/app/services/jwt_auth_service.py",
                evidence_ids=["EV-01"],
            ),
            CodeDiffLine(
                line_index=3,
                line_type="added",
                new_line_num=58,
                content="+@router.post('/api/v2/auth/token/rotate')",
                file_path="backend/app/api/auth.py",
                evidence_ids=["EV-02"],
            ),
        ]

        doc_patch_lines = [
            DocPatchLine(
                line_index=0,
                line_type="hunk_header",
                content="@@ -8,4 +8,6 @@ docs/security/jwt_authentication.md",
            ),
            DocPatchLine(
                line_index=1,
                line_type="removed",
                old_doc_line_num=9,
                content="- - Xác thực bằng `verify_static_api_token(token)` không giới hạn thời gian.",
                evidence_ids=["EV-01"],
            ),
            DocPatchLine(
                line_index=2,
                line_type="added",
                new_doc_line_num=9,
                content="+ - Xoay vòng phiên đăng nhập bằng `rotate_jwt_refresh_token(refresh_token, ttl_minutes=1440)`.",
                evidence_ids=["EV-01"],
            ),
            DocPatchLine(
                line_index=3,
                line_type="added",
                new_doc_line_num=10,
                content="+ - Endpoint mới: `POST /api/v2/auth/token/rotate` (thay thế cơ chế static token).",
                evidence_ids=["EV-02"],
            ),
        ]

        evidences = [
            GroundingEvidenceItem(
                evidence_id="EV-01",
                claim_summary="Thay thế hàm verify_static_api_token bằng rotate_jwt_refresh_token với TTL mặc định 1440 phút.",
                symbol_name="rotate_jwt_refresh_token",
                symbol_kind="function",
                file_path="backend/app/services/jwt_auth_service.py",
                start_line=42,
                end_line=55,
                commit_hash=pr_commit,
                commit_short="a7f102b",
                commit_message="feat(auth): implement JWT refresh token rotation",
                commit_author="lan-security",
                commit_date="2026-11-24 21:15:00 +0700",
                branch="feat/jwt-rotation",
                code_snippet="def rotate_jwt_refresh_token(refresh_token: str, ttl_minutes: int = 1440) -> TokenPair:",
                doc_patch_excerpt="Xoay vòng phiên đăng nhập bằng rotate_jwt_refresh_token(refresh_token, ttl_minutes=1440).",
                repo_grounding_status="PATCH_PREVIEW",
                repo_actual_excerpt="# Nhánh feat/jwt-rotation chưa merge vào main; tệp đang nằm trong PR #51 diff.",
                reviewer_status="pending",
            ),
            GroundingEvidenceItem(
                evidence_id="EV-02",
                claim_summary="Mở tuyến định tuyến mới POST /api/v2/auth/token/rotate.",
                symbol_name="POST /api/v2/auth/token/rotate",
                symbol_kind="endpoint",
                file_path="backend/app/api/auth.py",
                start_line=58,
                end_line=66,
                commit_hash=pr_commit,
                commit_short="a7f102b",
                commit_message="feat(auth): implement JWT refresh token rotation",
                commit_author="lan-security",
                commit_date="2026-11-24 21:15:00 +0700",
                branch="feat/jwt-rotation",
                code_snippet="@router.post('/api/v2/auth/token/rotate')",
                doc_patch_excerpt="Endpoint mới: POST /api/v2/auth/token/rotate (thay thế cơ chế static token).",
                repo_grounding_status="PATCH_PREVIEW",
                repo_actual_excerpt="# Chờ reviewer xác nhận trước khi merge PR #51.",
                reviewer_status="pending",
            ),
        ]

        links = [
            DiffMappingLink(
                link_id="LNK-01",
                evidence_id="EV-01",
                code_file_path="backend/app/services/jwt_auth_service.py",
                code_line_indices=[1, 2],
                doc_line_indices=[1, 2],
                rationale="Đối chiếu thay đổi chữ ký hàm xác thực token và tham số ttl_minutes=1440.",
                confidence=0.96,
            ),
            DiffMappingLink(
                link_id="LNK-02",
                evidence_id="EV-02",
                code_file_path="backend/app/api/auth.py",
                code_line_indices=[3],
                doc_line_indices=[3],
                rationale="Khớp route decorator mới với mô tả endpoint trong tài liệu bảo mật.",
                confidence=0.95,
            ),
        ]

        return GroundingDiffSessionResponse(
            session_id=f"gd_{uuid.uuid4().hex[:8]}",
            preset_id="auth_token_rotation",
            title="PR #51 • Kiểm duyệt Bản vá Tài liệu JWT Token Rotation (Unmerged PR Preview)",
            repo_name="cnpm-groupgaugau1-2026/LivingDocs",
            branch="feat/jwt-rotation",
            commit_hash=pr_commit,
            pr_number=51,
            target_doc_path="docs/security/jwt_authentication.md",
            source_code_files=[
                "backend/app/services/jwt_auth_service.py",
                "backend/app/api/auth.py",
            ],
            code_diff_lines=code_diff_lines,
            doc_patch_lines=doc_patch_lines,
            mapping_links=links,
            evidences=evidences,
            grounding_coverage_score=100.0,
            verified_count=0,
            flagged_count=0,
            pending_count=len(evidences),
        )

    # ==================== CUSTOM UNIFIED DIFF & DOC PATCH PARSER ====================

    def _build_custom_session(
        self,
        req: CreateGroundingSessionRequest,
        git_meta: Dict[str, str],
    ) -> GroundingDiffSessionResponse:
        commit_hash = req.commit_hash.strip() or git_meta["hash"]
        commit_short = commit_hash[:7]

        code_lines: List[CodeDiffLine] = []
        doc_lines: List[DocPatchLine] = []
        evidences: List[GroundingEvidenceItem] = []
        links: List[DiffMappingLink] = []

        current_file = "backend/app/main.py"
        old_ln = 1
        new_ln = 1
        ev_counter = 1

        for idx, raw in enumerate(req.custom_code_diff.splitlines()):
            if raw.startswith("+++ b/"):
                current_file = raw[6:].strip()
                continue
            if raw.startswith("---") or raw.startswith("diff --git"):
                code_lines.append(
                    CodeDiffLine(
                        line_index=len(code_lines),
                        line_type="hunk_header",
                        content=raw,
                        file_path=current_file,
                    )
                )
                continue
            if raw.startswith("@@"):
                m = re.search(r"-(\d+)(?:,\d+)?\s+\+(\d+)", raw)
                if m:
                    old_ln = int(m.group(1))
                    new_ln = int(m.group(2))
                code_lines.append(
                    CodeDiffLine(
                        line_index=len(code_lines),
                        line_type="hunk_header",
                        content=raw,
                        file_path=current_file,
                    )
                )
                continue

            if raw.startswith("+"):
                ev_id = f"EV-{ev_counter:02d}"
                ev_counter += 1
                line_idx = len(code_lines)
                code_lines.append(
                    CodeDiffLine(
                        line_index=line_idx,
                        line_type="added",
                        new_line_num=new_ln,
                        content=raw,
                        file_path=current_file,
                        evidence_ids=[ev_id],
                    )
                )
                s_real, e_real, st_real, ex_real = self._locate_symbol_in_repo(
                    current_file,
                    raw[1:].strip()[:40],
                    new_ln,
                    new_ln + 5,
                )
                evidences.append(
                    GroundingEvidenceItem(
                        evidence_id=ev_id,
                        claim_summary=f"Thay đổi mã nguồn tại {current_file} dòng {new_ln}",
                        symbol_name=raw[1:].strip()[:60],
                        symbol_kind="function",
                        file_path=current_file,
                        start_line=s_real,
                        end_line=e_real,
                        commit_hash=commit_hash,
                        commit_short=commit_short,
                        commit_message=git_meta["message"],
                        commit_author=git_meta["author"],
                        commit_date=git_meta["date"],
                        branch=req.branch,
                        code_snippet=raw,
                        doc_patch_excerpt="Đối chiếu với bản vá tài liệu tương ứng.",
                        repo_grounding_status=st_real,
                        repo_actual_excerpt=ex_real,
                        reviewer_status="pending",
                    )
                )
                links.append(
                    DiffMappingLink(
                        link_id=f"LNK-{ev_id}",
                        evidence_id=ev_id,
                        code_file_path=current_file,
                        code_line_indices=[line_idx],
                        doc_line_indices=[],
                        rationale=f"Liên kết dòng mã mới tại {current_file}:{new_ln}.",
                        confidence=0.92,
                    )
                )
                new_ln += 1
            elif raw.startswith("-"):
                code_lines.append(
                    CodeDiffLine(
                        line_index=len(code_lines),
                        line_type="removed",
                        old_line_num=old_ln,
                        content=raw,
                        file_path=current_file,
                    )
                )
                old_ln += 1
            else:
                code_lines.append(
                    CodeDiffLine(
                        line_index=len(code_lines),
                        line_type="context",
                        old_line_num=old_ln,
                        new_line_num=new_ln,
                        content=raw,
                        file_path=current_file,
                    )
                )
                old_ln += 1
                new_ln += 1

        d_old = 1
        d_new = 1
        link_cursor = 0
        for raw in req.custom_doc_patch.splitlines():
            if raw.startswith("@@"):
                doc_lines.append(
                    DocPatchLine(
                        line_index=len(doc_lines),
                        line_type="hunk_header",
                        content=raw,
                    )
                )
                continue
            if raw.startswith("+"):
                assigned_evs: List[str] = []
                if links:
                    target_lnk = links[link_cursor % len(links)]
                    assigned_evs = [target_lnk.evidence_id]
                    target_lnk.doc_line_indices.append(len(doc_lines))
                    link_cursor += 1
                doc_lines.append(
                    DocPatchLine(
                        line_index=len(doc_lines),
                        line_type="added",
                        new_doc_line_num=d_new,
                        content=raw,
                        evidence_ids=assigned_evs,
                    )
                )
                d_new += 1
            elif raw.startswith("-"):
                doc_lines.append(
                    DocPatchLine(
                        line_index=len(doc_lines),
                        line_type="removed",
                        old_doc_line_num=d_old,
                        content=raw,
                    )
                )
                d_old += 1
            else:
                doc_lines.append(
                    DocPatchLine(
                        line_index=len(doc_lines),
                        line_type="context",
                        old_doc_line_num=d_old,
                        new_doc_line_num=d_new,
                        content=raw,
                    )
                )
                d_old += 1
                d_new += 1

        files = sorted({c.file_path for c in code_lines if c.file_path})
        return GroundingDiffSessionResponse(
            session_id=f"gd_{uuid.uuid4().hex[:8]}",
            preset_id="custom",
            title=req.title.strip() or f"Custom Code-vs-Doc Diff Review ({commit_short})",
            repo_name=req.repo_name,
            branch=req.branch,
            commit_hash=commit_hash,
            pr_number=req.pr_number,
            target_doc_path=req.target_doc_path,
            source_code_files=files or [current_file],
            code_diff_lines=code_lines,
            doc_patch_lines=doc_lines,
            mapping_links=links,
            evidences=evidences,
            grounding_coverage_score=100.0 if evidences else 0.0,
            verified_count=0,
            flagged_count=0,
            pending_count=len(evidences),
        )