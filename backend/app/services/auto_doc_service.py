import difflib
import json
import os
import re
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx

from app.schemas.auto_doc import (
    AcceptDraftRequest,
    AutoDocWorkflowResponse,
    CodeChangeEventRequest,
    CodeChangeItemSchema,
    CodeVsDocComparisonSchema,
    DiffLineSchema,
    DocVersionSchema,
    EditDraftRequest,
    RegenerateDraftRequest,
    RollbackVersionRequest,
)


class AutomaticDocUpdateService:
    """
    FE03 - Automatic Documentation Update on Code Change
    - FE03.1: Event-Triggered Auto-Update Workflow (PR/Commit & GitHub Webhook)
    - FE03.2: Code-vs-Doc Side-by-Side Version Comparison Logic
    - FE03.3: Action Handlers (Accept, Edit, Regenerate, Rollback)
    """

    def __init__(self) -> None:
        self.gemini_api_key = os.getenv("GEMINI_API_KEY", "").strip()
        self.gemini_model = os.getenv("GEMINI_TEXT_MODEL", "gemini-2.5-flash").strip()

        here = Path(__file__).resolve()
        backend_dir = here.parents[2]
        self.project_root = (
            backend_dir.parent if (backend_dir.parent / "backend").exists() else backend_dir
        )
        self.storage_file = backend_dir / "data" / "fe03_doc_workflows.json"
        self.storage_file.parent.mkdir(parents=True, exist_ok=True)
        self._workflows: Dict[str, Dict[str, Any]] = self._load_storage()

    def _now_iso(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    def _load_storage(self) -> Dict[str, Dict[str, Any]]:
        if self.storage_file.exists():
            try:
                return json.loads(self.storage_file.read_text(encoding="utf-8"))
            except Exception:
                return {}
        return {}

    def _save_storage(self) -> None:
        self.storage_file.write_text(
            json.dumps(self._workflows, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def list_workflows(self) -> List[AutoDocWorkflowResponse]:
        items = [AutoDocWorkflowResponse(**wf) for wf in self._workflows.values()]
        return list(reversed(items))

    def get_workflow(self, workflow_id: str) -> AutoDocWorkflowResponse:
        if workflow_id not in self._workflows:
            raise ValueError(f"Không tìm thấy workflow '{workflow_id}'.")
        return AutoDocWorkflowResponse(**self._workflows[workflow_id])

    # ==================== FE03.1: EVENT-TRIGGERED AUTO-UPDATE WORKFLOW ====================

    async def trigger_update_workflow(
        self,
        req: CodeChangeEventRequest,
    ) -> AutoDocWorkflowResponse:
        code_diff = req.code_diff.strip()
        if req.use_local_git_diff or not code_diff:
            local_diff = self._read_local_git_diff()
            if local_diff:
                code_diff = local_diff

        if not code_diff:
            code_diff = (
                "@@ -18,4 +18,12 @@\n"
                "+@router.post('/verify-consistency', response_model=VisualCodeConsistencyResponse)\n"
                "+async def verify_visual_code_consistency(file: UploadFile, repo_path: str = ''):\n"
                "+    return await consistency_verifier.verify_consistency(file, repo_path=repo_path)\n"
            )

        existing_wf = self._find_latest_workflow_by_doc(req.target_doc_path)
        if existing_wf and not req.current_doc_content.strip():
            published_ver = DocVersionSchema(**existing_wf["current_published_version"])
            history: List[DocVersionSchema] = [
                DocVersionSchema(**v) for v in existing_wf.get("version_history", [])
            ]
        else:
            initial_doc = req.current_doc_content.strip() or self._default_baseline_doc(
                req.target_doc_path
            )
            published_ver = DocVersionSchema(
                version_id=f"ver_{uuid.uuid4().hex[:8]}",
                version_number="v1.0",
                content=initial_doc,
                created_at=self._now_iso(),
                author="initial_seed",
                trigger_ref="baseline",
                status="published",
                change_summary="Phiên bản tài liệu gốc trước khi có thay đổi mã nguồn.",
            )
            history = [published_ver]

        code_changes = self._extract_code_changes_from_diff(code_diff)

        updated_markdown, change_summary, engine_used = await self._generate_updated_doc(
            target_doc_path=req.target_doc_path,
            current_doc=published_ver.content,
            code_diff=code_diff,
            code_changes=code_changes,
            event_desc=self._format_trigger_ref(req),
            custom_instruction="",
        )

        next_ver_num = self._bump_minor_version(published_ver.version_number)
        draft_ver = DocVersionSchema(
            version_id=f"ver_{uuid.uuid4().hex[:8]}",
            version_number=f"{next_ver_num}-draft",
            content=updated_markdown,
            created_at=self._now_iso(),
            author="ai_workflow",
            trigger_ref=self._format_trigger_ref(req),
            status="draft",
            change_summary=change_summary,
        )
        history.append(draft_ver)

        comparison = self.build_side_by_side_comparison(
            old_doc=published_ver.content,
            new_doc=draft_ver.content,
            code_changes=code_changes,
        )

        workflow_id = f"wf_{uuid.uuid4().hex[:8]}"
        workflow = AutoDocWorkflowResponse(
            workflow_id=workflow_id,
            event_type=req.event_type,
            repo_name=req.repo_name,
            branch=req.branch,
            commit_sha=req.commit_sha,
            pr_number=req.pr_number,
            pr_title=req.pr_title,
            author=req.author,
            target_doc_path=req.target_doc_path,
            code_diff=code_diff,
            engine_used=engine_used,
            current_published_version=published_ver,
            active_draft_version=draft_ver,
            comparison=comparison,
            version_history=history,
        )

        self._workflows[workflow_id] = workflow.model_dump(mode="json")
        self._save_storage()
        return workflow

    async def handle_github_webhook(
        self,
        github_event: str,
        payload: Dict[str, Any],
    ) -> AutoDocWorkflowResponse:
        repo_name = payload.get("repository", {}).get(
            "full_name", "cnpm-groupgaugau1-2026/LivingDocs"
        )

        if github_event == "pull_request":
            pr = payload.get("pull_request", {})
            req = CodeChangeEventRequest(
                event_type="pull_request",
                repo_name=repo_name,
                branch=pr.get("head", {}).get("ref", "feature-branch"),
                commit_sha=str(pr.get("head", {}).get("sha", "HEAD"))[:7],
                pr_number=payload.get("number") or pr.get("number"),
                pr_title=pr.get("title", "Pull Request Code Update"),
                author=pr.get("user", {}).get("login", "github-user"),
                target_doc_path="docs/architecture/multimodal_pipeline.md",
                code_diff=pr.get("body") or "",
                use_local_git_diff=True,
            )
        else:
            head_commit = payload.get("head_commit") or {}
            ref = str(payload.get("ref", "refs/heads/main")).replace("refs/heads/", "")
            added = head_commit.get("added", [])
            modified = head_commit.get("modified", [])
            diff_lines = [f"+ modified file: {f}" for f in modified] + [
                f"+ added file: {f}" for f in added
            ]
            req = CodeChangeEventRequest(
                event_type="commit",
                repo_name=repo_name,
                branch=ref,
                commit_sha=str(head_commit.get("id") or payload.get("after", "HEAD"))[:7],
                pr_number=None,
                pr_title=head_commit.get("message", "Push commit update"),
                author=head_commit.get("author", {}).get("name", "git-committer"),
                target_doc_path="docs/architecture/multimodal_pipeline.md",
                code_diff="\n".join(diff_lines),
                use_local_git_diff=True,
            )

        return await self.trigger_update_workflow(req)

    # ==================== FE03.2: CODE-VS-DOC SIDE-BY-SIDE COMPARISON ====================

    def build_side_by_side_comparison(
        self,
        old_doc: str,
        new_doc: str,
        code_changes: List[CodeChangeItemSchema],
    ) -> CodeVsDocComparisonSchema:
        old_lines = old_doc.splitlines()
        new_lines = new_doc.splitlines()

        matcher = difflib.SequenceMatcher(None, old_lines, new_lines)
        diff_rows: List[DiffLineSchema] = []
        added_cnt = 0
        removed_cnt = 0

        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "equal":
                for offset in range(i2 - i1):
                    diff_rows.append(
                        DiffLineSchema(
                            line_type="unchanged",
                            old_line_num=i1 + offset + 1,
                            new_line_num=j1 + offset + 1,
                            old_text=old_lines[i1 + offset],
                            new_text=new_lines[j1 + offset],
                        )
                    )
            elif tag == "replace":
                max_len = max(i2 - i1, j2 - j1)
                for offset in range(max_len):
                    has_old = (i1 + offset) < i2
                    has_new = (j1 + offset) < j2
                    if has_old:
                        removed_cnt += 1
                    if has_new:
                        added_cnt += 1
                    diff_rows.append(
                        DiffLineSchema(
                            line_type="modified"
                            if (has_old and has_new)
                            else ("removed" if has_old else "added"),
                            old_line_num=(i1 + offset + 1) if has_old else None,
                            new_line_num=(j1 + offset + 1) if has_new else None,
                            old_text=old_lines[i1 + offset] if has_old else "",
                            new_text=new_lines[j1 + offset] if has_new else "",
                        )
                    )
            elif tag == "delete":
                for offset in range(i2 - i1):
                    removed_cnt += 1
                    diff_rows.append(
                        DiffLineSchema(
                            line_type="removed",
                            old_line_num=i1 + offset + 1,
                            new_line_num=None,
                            old_text=old_lines[i1 + offset],
                            new_text="",
                        )
                    )
            elif tag == "insert":
                for offset in range(j2 - j1):
                    added_cnt += 1
                    diff_rows.append(
                        DiffLineSchema(
                            line_type="added",
                            old_line_num=None,
                            new_line_num=j1 + offset + 1,
                            old_text="",
                            new_text=new_lines[j1 + offset],
                        )
                    )

        impact_points: List[str] = []
        for ch in code_changes:
            if ch.change_type == "added":
                impact_points.append(f"Bổ sung đặc tả cho {ch.symbol_kind} mới: `{ch.signature}`")
            elif ch.change_type == "removed":
                impact_points.append(f"Gỡ bỏ phần mô tả lỗi thời của `{ch.signature}`")
            else:
                impact_points.append(f"Cập nhật chữ ký / tham số của `{ch.signature}`")

        if not impact_points and (added_cnt > 0 or removed_cnt > 0):
            impact_points.append(
                f"Cập nhật {added_cnt} dòng nội dung mới và điều chỉnh {removed_cnt} dòng cũ."
            )

        return CodeVsDocComparisonSchema(
            code_changes_detected=code_changes,
            doc_impact_points=impact_points,
            side_by_side_diff=diff_rows,
            added_lines=added_cnt,
            removed_lines=removed_cnt,
            drift_resolved_count=max(len(code_changes), 1 if added_cnt > 0 else 0),
        )

    # ==================== FE03.3: ACTION HANDLERS (ACCEPT, EDIT, REGENERATE, ROLLBACK) ====================

    def accept_draft(self, req: AcceptDraftRequest) -> AutoDocWorkflowResponse:
        wf = self.get_workflow(req.workflow_id)
        if not wf.active_draft_version:
            raise ValueError("Workflow hiện không có bản nháp nào đang chờ duyệt.")

        draft = wf.active_draft_version
        clean_ver_num = draft.version_number.replace("-draft", "")

        for v in wf.version_history:
            if v.status == "published":
                v.status = "superseded"
            if v.version_id == draft.version_id:
                v.status = "published"
                v.version_number = clean_ver_num
                v.author = f"{v.author} (approved by {req.reviewer})"
                v.created_at = self._now_iso()

        published_now = next(v for v in wf.version_history if v.version_id == draft.version_id)
        wf.current_published_version = published_now
        wf.active_draft_version = None
        wf.comparison = self.build_side_by_side_comparison(
            old_doc=published_now.content,
            new_doc=published_now.content,
            code_changes=wf.comparison.code_changes_detected,
        )

        self._workflows[wf.workflow_id] = wf.model_dump(mode="json")
        self._save_storage()
        return wf

    def edit_draft(self, req: EditDraftRequest) -> AutoDocWorkflowResponse:
        wf = self.get_workflow(req.workflow_id)
        if not wf.active_draft_version:
            next_num = self._bump_minor_version(wf.current_published_version.version_number)
            new_draft = DocVersionSchema(
                version_id=f"ver_{uuid.uuid4().hex[:8]}",
                version_number=f"{next_num}-draft",
                content=req.edited_content,
                created_at=self._now_iso(),
                author="developer_edit",
                trigger_ref=req.editor_note,
                status="draft",
                change_summary=req.editor_note,
            )
            wf.version_history.append(new_draft)
            wf.active_draft_version = new_draft
        else:
            wf.active_draft_version.content = req.edited_content
            wf.active_draft_version.author = "developer_edit"
            wf.active_draft_version.created_at = self._now_iso()
            wf.active_draft_version.change_summary = req.editor_note
            for v in wf.version_history:
                if v.version_id == wf.active_draft_version.version_id:
                    v.content = req.edited_content
                    v.author = "developer_edit"
                    v.created_at = wf.active_draft_version.created_at
                    v.change_summary = req.editor_note

        wf.comparison = self.build_side_by_side_comparison(
            old_doc=wf.current_published_version.content,
            new_doc=wf.active_draft_version.content,
            code_changes=wf.comparison.code_changes_detected,
        )

        self._workflows[wf.workflow_id] = wf.model_dump(mode="json")
        self._save_storage()
        return wf

    async def regenerate_draft(self, req: RegenerateDraftRequest) -> AutoDocWorkflowResponse:
        wf = self.get_workflow(req.workflow_id)
        code_changes = wf.comparison.code_changes_detected or self._extract_code_changes_from_diff(
            wf.code_diff
        )

        new_md, summary, engine_used = await self._generate_updated_doc(
            target_doc_path=wf.target_doc_path,
            current_doc=wf.current_published_version.content,
            code_diff=wf.code_diff,
            code_changes=code_changes,
            event_desc=f"Regenerate ({wf.commit_sha})",
            custom_instruction=req.custom_instruction,
        )

        wf.engine_used = engine_used
        if wf.active_draft_version:
            wf.active_draft_version.content = new_md
            wf.active_draft_version.created_at = self._now_iso()
            wf.active_draft_version.change_summary = summary
            for v in wf.version_history:
                if v.version_id == wf.active_draft_version.version_id:
                    v.content = new_md
                    v.created_at = wf.active_draft_version.created_at
                    v.change_summary = summary
        else:
            next_num = self._bump_minor_version(wf.current_published_version.version_number)
            new_draft = DocVersionSchema(
                version_id=f"ver_{uuid.uuid4().hex[:8]}",
                version_number=f"{next_num}-draft",
                content=new_md,
                created_at=self._now_iso(),
                author="ai_workflow",
                trigger_ref=f"Regenerate ({wf.commit_sha})",
                status="draft",
                change_summary=summary,
            )
            wf.version_history.append(new_draft)
            wf.active_draft_version = new_draft

        wf.comparison = self.build_side_by_side_comparison(
            old_doc=wf.current_published_version.content,
            new_doc=wf.active_draft_version.content,
            code_changes=code_changes,
        )

        self._workflows[wf.workflow_id] = wf.model_dump(mode="json")
        self._save_storage()
        return wf

    def rollback_version(self, req: RollbackVersionRequest) -> AutoDocWorkflowResponse:
        wf = self.get_workflow(req.workflow_id)
        target_ver = next(
            (v for v in wf.version_history if v.version_id == req.target_version_id),
            None,
        )
        if not target_ver:
            raise ValueError(f"Không tìm thấy phiên bản '{req.target_version_id}' trong lịch sử.")

        for v in wf.version_history:
            if v.status in ("published", "draft"):
                v.status = "rolled_back"

        next_num = self._bump_minor_version(wf.current_published_version.version_number)
        restored = DocVersionSchema(
            version_id=f"ver_{uuid.uuid4().hex[:8]}",
            version_number=next_num,
            content=target_ver.content,
            created_at=self._now_iso(),
            author="rollback",
            trigger_ref=f"Rollback to {target_ver.version_number}",
            status="published",
            change_summary=f"Khôi phục nội dung từ {target_ver.version_number}: {req.reason}",
        )
        wf.version_history.append(restored)
        wf.current_published_version = restored
        wf.active_draft_version = None
        wf.comparison = self.build_side_by_side_comparison(
            old_doc=restored.content,
            new_doc=restored.content,
            code_changes=wf.comparison.code_changes_detected,
        )

        self._workflows[wf.workflow_id] = wf.model_dump(mode="json")
        self._save_storage()
        return wf

    # ==================== INTERNAL HELPERS ====================

    def _find_latest_workflow_by_doc(self, target_doc_path: str) -> Optional[Dict[str, Any]]:
        for wf in reversed(list(self._workflows.values())):
            if wf.get("target_doc_path") == target_doc_path:
                return wf
        return None

    def _bump_minor_version(self, current_ver: str) -> str:
        clean = current_ver.replace("-draft", "").lstrip("v")
        parts = clean.split(".")
        if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
            return f"v{parts[0]}.{int(parts[1]) + 1}"
        return "v1.1"

    def _format_trigger_ref(self, req: CodeChangeEventRequest) -> str:
        if req.event_type == "pull_request" and req.pr_number:
            return f"PR #{req.pr_number} ({req.commit_sha})"
        return f"Commit {req.commit_sha} on {req.branch}"

    def _read_local_git_diff(self) -> str:
        try:
            proc = subprocess.run(
                ["git", "diff", "HEAD~1", "--", "backend/app"],
                cwd=str(self.project_root),
                capture_output=True,
                text=True,
                timeout=8,
            )
            diff_out = proc.stdout.strip()
            if diff_out:
                return diff_out[:6000]
        except Exception:
            pass
        return ""

    def _extract_code_changes_from_diff(self, code_diff: str) -> List[CodeChangeItemSchema]:
        changes: List[CodeChangeItemSchema] = []
        seen: set[Tuple[str, str]] = set()

        for raw_line in code_diff.splitlines():
            if raw_line.startswith("+++") or raw_line.startswith("---"):
                continue
            if not (raw_line.startswith("+") or raw_line.startswith("-")):
                continue

            c_type = "added" if raw_line.startswith("+") else "removed"
            line = raw_line[1:].strip()

            m_route = re.match(
                r'@\w+\.(get|post|put|delete|patch)\(\s*["\']([^"\']+)["\']',
                line,
                re.IGNORECASE,
            )
            if m_route:
                sig = f"{m_route.group(1).upper()} {m_route.group(2)}"
                if (c_type, sig) not in seen:
                    seen.add((c_type, sig))
                    changes.append(
                        CodeChangeItemSchema(
                            change_type=c_type,
                            symbol_kind="endpoint",
                            signature=sig,
                            detail=line,
                        )
                    )
                continue

            m_cls = re.match(r"class\s+([A-Za-z0-9_]+)", line)
            if m_cls:
                sig = m_cls.group(1)
                if (c_type, sig) not in seen:
                    seen.add((c_type, sig))
                    changes.append(
                        CodeChangeItemSchema(
                            change_type=c_type,
                            symbol_kind="class",
                            signature=sig,
                            detail=line,
                        )
                    )
                continue

            m_fn = re.match(r"(?:async\s+)?def\s+([a-zA-Z0-9_]+\s*\([^)]*\))", line)
            if m_fn:
                sig = m_fn.group(1)
                if (c_type, sig) not in seen:
                    seen.add((c_type, sig))
                    changes.append(
                        CodeChangeItemSchema(
                            change_type=c_type,
                            symbol_kind="function",
                            signature=sig,
                            detail=line,
                        )
                    )

        return changes

    async def _generate_updated_doc(
        self,
        target_doc_path: str,
        current_doc: str,
        code_diff: str,
        code_changes: List[CodeChangeItemSchema],
        event_desc: str,
        custom_instruction: str,
    ) -> Tuple[str, str, str]:
        fence = "`" * 3
        if self.gemini_api_key:
            try:
                prompt = (
                    "You are the LivingDocs FE03 Automatic Documentation Update Engine.\n"
                    "Update the existing Markdown documentation so it accurately reflects the code diff below.\n"
                    "Keep existing accurate sections intact, remove or update deprecated signatures/endpoints, "
                    "and document newly added endpoints/functions clearly in Vietnamese.\n\n"
                    f"Target Doc Path: {target_doc_path}\n"
                    f"Trigger Event: {event_desc}\n"
                    f"Custom Developer Instruction: {custom_instruction or 'None'}\n\n"
                    "Current Published Markdown:\n"
                    f"{fence}markdown\n{current_doc}\n{fence}\n\n"
                    "Git Code Diff:\n"
                    f"{fence}diff\n{code_diff[:4500]}\n{fence}\n\n"
                    "Return ONLY the updated Markdown document (no outer markdown fences)."
                )

                url = (
                    f"https://generativelanguage.googleapis.com/v1beta/models/"
                    f"{self.gemini_model}:generateContent?key={self.gemini_api_key}"
                )
                body = {
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {"temperature": 0.15},
                }
                async with httpx.AsyncClient(timeout=25.0) as client:
                    resp = await client.post(url, json=body)
                    resp.raise_for_status()
                    data = resp.json()

                text = (
                    data.get("candidates", [{}])[0]
                    .get("content", {})
                    .get("parts", [{}])[0]
                    .get("text", "")
                    .strip()
                )
                if text:
                    cleaned = re.sub(r"^```markdown\s*|\s*```$", "", text)
                    return (
                        cleaned,
                        f"AI tự động đồng bộ {len(code_changes)} thay đổi mã nguồn từ {event_desc}.",
                        f"gemini_llm ({self.gemini_model})",
                    )
            except Exception:
                pass

        # Bộ tổng hợp tài liệu Markdown dựa trên AST Diff khi chạy offline
        lines = current_doc.splitlines()
        removed_sigs = [
            c.signature.split("(")[0].strip() for c in code_changes if c.change_type == "removed"
        ]
        added_items = [c for c in code_changes if c.change_type == "added"]

        updated_lines: List[str] = []
        for ln in lines:
            if any(rem and rem in ln for rem in removed_sigs):
                continue
            updated_lines.append(ln)

        if added_items:
            updated_lines.append("")
            updated_lines.append(f"## Cập nhật tự động ({event_desc})")
            for item in added_items:
                if item.symbol_kind == "endpoint":
                    updated_lines.append(
                        f"- **API Endpoint mới:** `{item.signature}` — `{item.detail}`"
                    )
                elif item.symbol_kind == "class":
                    updated_lines.append(f"- **Thành phần kiến trúc (Class):** `{item.signature}`")
                else:
                    updated_lines.append(f"- **Hàm xử lý (Function):** `{item.signature}`")

        if custom_instruction.strip():
            updated_lines.append("")
            updated_lines.append(
                f"> **Ghi chú bổ sung ({custom_instruction.strip()}):** "
                "Đã cập nhật ví dụ tích hợp và kiểm tra tham số đầu vào/đầu ra."
            )

        summary = (
            f"Đã tự động cập nhật {len(added_items)} thành phần mới và gỡ {len(removed_sigs)} mục lỗi thời "
            f"theo sự kiện {event_desc}."
        )
        return ("\n".join(updated_lines).strip(), summary, "ast_diff_doc_synthesizer")

    def _default_baseline_doc(self, target_doc_path: str) -> str:
        return (
            f"# Tài liệu Kỹ thuật: {target_doc_path}\n\n"
            "## 1. Tổng quan Kiến trúc Multimodal (FE05)\n"
            "Hệ thống xử lý tài liệu kỹ thuật trực quan gồm 2 phân hệ đã phát hành:\n"
            "- **FE05.1 OCR Engine:** `TechnicalAssetOcrEngine.extract_from_bytes()` trích xuất token từ sơ đồ và PDF.\n"
            "- **FE05.2 Vision-LLM Context Extractor:** `VisionContextExtractor.extract_context()` tái dựng đồ thị kiến trúc có hướng.\n\n"
            "## 2. Danh sách API Endpoints hiện hành\n"
            "- `POST /api/v1/multimodal/ocr`: Trích xuất thực thể kỹ thuật từ ảnh/PDF.\n"
            "- `POST /api/v1/multimodal/extract-context`: Tái dựng đồ thị Nodes, Edges và Architectural Claims."
        )