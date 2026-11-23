import json
import os
from typing import Any, Dict, List, Optional, Tuple

import httpx
from sqlalchemy.orm import Session

from app.api.v1.admin_ai_config import AIParameterConfig, _get_or_create_config
from app.core.config import settings
from app.models.template import DocTemplate
from app.schemas.ast_doc import (
    ASTParseResponse,
    CoverageReport,
    DraftGenerationRequest,
    DraftGenerationResponse,
)
from app.services.ast_parser_service import ast_parser_service
from app.services.coverage_analyzer_service import coverage_analyzer_service


DEFAULT_AST_TEMPLATE = """# Tài liệu Kỹ thuật: {{file_path}}

## 1. Tổng quan Module
- **Tệp nguồn:** `{{file_path}}`
- **Ngôn ngữ:** `{{language}}`
- **Độ phủ tài liệu hiện tại:** {{coverage_percentage}}% ({{documented_entities}}/{{total_entities}} thực thể)

## 2. Kiến trúc Class & Thành phần chính
{{classes_section}}

## 3. Chi tiết Hàm & Phương thức (API Reference)
{{functions_section}}

## 4. Đề xuất bổ sung tài liệu (Coverage Gaps)
{{gaps_section}}
"""


class AIDocGeneratorService:
    """Module 4.3: Template-Guided AI Draft Generation Pipeline."""

    async def generate_draft(
        self, payload: DraftGenerationRequest, db: Session
    ) -> DraftGenerationResponse:
        warnings: List[str] = []

        # 1. Phân tích AST (4.1) & Đánh giá lỗ hổng độ phủ (4.2)
        ast_result: ASTParseResponse = ast_parser_service.parse_code(
            file_path=payload.file_path,
            source_code=payload.source_code,
            language=payload.language,
        )
        coverage_report: CoverageReport = coverage_analyzer_service.analyze_ast(ast_result)

        # 2. Lấy cấu hình AI Engine từ FE13
        ai_config: AIParameterConfig = _get_or_create_config(db)
        if (
            ai_config.auto_pause_on_exceed
            and ai_config.current_daily_tokens_used >= ai_config.daily_token_budget
        ):
            warnings.append(
                "Ngân sách token hàng ngày đã đạt giới hạn cấu hình trong FE13; hệ thống chuyển sang chế độ tổng hợp AST cục bộ."
            )

        # 3. Lấy mẫu tài liệu từ FE11 (DocTemplate)
        template_obj = self._resolve_template(db, payload.template_id, payload.template_slug)
        if template_obj:
            template_name = f"{template_obj.name} ({template_obj.current_version})"
            template_content = template_obj.content
            placeholder_mappings = self._safe_json_loads(
                template_obj.placeholder_mappings_json, default=[]
            )
            formatting_constraints = self._safe_json_loads(
                template_obj.formatting_constraints_json, default={}
            )
        else:
            template_name = "Built-in AST Technical Specification (Default)"
            template_content = DEFAULT_AST_TEMPLATE
            placeholder_mappings = []
            formatting_constraints = {"format": "markdown", "language": "vi"}
            if payload.template_id or payload.template_slug:
                warnings.append(
                    "Không tìm thấy Template yêu cầu trong DB; đang sử dụng mẫu chuẩn AST mặc định."
                )

        # 4. Xây dựng Prompt kết hợp AST + Coverage + Template
        system_prompt, user_prompt = self._build_prompts(
            ast_result=ast_result,
            coverage_report=coverage_report,
            template_name=template_name,
            template_content=template_content,
            placeholder_mappings=placeholder_mappings,
            formatting_constraints=formatting_constraints,
            custom_instructions=payload.custom_instructions,
            include_gaps=payload.include_coverage_gaps,
        )

        estimated_tokens = max(120, (len(system_prompt) + len(user_prompt)) // 4)
        budget_blocked = (
            ai_config.auto_pause_on_exceed
            and ai_config.current_daily_tokens_used >= ai_config.daily_token_budget
        )

        # 5. Thực thi gọi LLM (nếu có API key & còn ngân sách), ngược lại dùng AST Template Engine
        markdown_output: Optional[str] = None
        provider_used = ai_config.primary_provider
        model_used = ai_config.primary_model
        generation_mode = "ast_template_fallback"

        if not budget_blocked:
            llm_res = await self._try_call_llm(
                ai_config=ai_config,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                warnings=warnings,
            )
            if llm_res:
                markdown_output, provider_used, model_used, actual_tokens = llm_res
                generation_mode = "llm_live"
                estimated_tokens = actual_tokens

        if not markdown_output:
            provider_used = "livingdocs-ast-engine"
            model_used = "tree-sitter-deterministic-v1"
            markdown_output = self._render_deterministic_draft(
                ast_result=ast_result,
                coverage_report=coverage_report,
                template_content=template_content,
                custom_instructions=payload.custom_instructions,
            )

        # 6. Cập nhật thống kê token sử dụng vào bảng cấu hình FE13
        ai_config.current_daily_tokens_used = (
            ai_config.current_daily_tokens_used or 0
        ) + estimated_tokens
        db.commit()

        return DraftGenerationResponse(
            file_path=ast_result.file_path,
            language=ast_result.language,
            template_used=template_name,
            generation_mode=generation_mode,
            provider_used=provider_used,
            model_used=model_used,
            tokens_estimated=estimated_tokens,
            markdown_content=markdown_output,
            ast_summary=ast_result,
            coverage_report=coverage_report,
            warnings=warnings,
        )

    def _resolve_template(
        self,
        db: Session,
        template_id: Optional[int],
        template_slug: Optional[str],
    ) -> Optional[DocTemplate]:
        if template_id is not None:
            return db.query(DocTemplate).filter(DocTemplate.id == template_id).first()
        if template_slug:
            return db.query(DocTemplate).filter(DocTemplate.slug == template_slug).first()
        return (
            db.query(DocTemplate)
            .filter(DocTemplate.is_enforced.is_(True))
            .order_by(DocTemplate.id.asc())
            .first()
        )

    def _safe_json_loads(self, raw: Optional[str], default: Any) -> Any:
        if not raw:
            return default
        try:
            return json.loads(raw)
        except Exception:
            return default

    def _build_prompts(
        self,
        ast_result: ASTParseResponse,
        coverage_report: CoverageReport,
        template_name: str,
        template_content: str,
        placeholder_mappings: List[Any],
        formatting_constraints: Dict[str, Any],
        custom_instructions: Optional[str],
        include_gaps: bool,
    ) -> Tuple[str, str]:
        system_prompt = (
            "Bạn là kỹ sư kiến trúc phần mềm chuyên viết tài liệu kỹ thuật chuẩn doanh nghiệp cho nền tảng LivingDocs. "
            "Nhiệm vụ của bạn là sinh tài liệu Markdown chính xác dựa trên cây cú pháp trừu tượng (AST) đã trích xuất, "
            "tuân thủ tuyệt đối cấu trúc của Template được cung cấp và không bịa đặt hàm/tham số không tồn tại trong AST."
        )

        ast_compact = ast_result.model_dump()
        prompt_parts = [
            f"### TEMPLATE MỤC TIÊU: {template_name}",
            "```markdown",
            template_content,
            "```",
            f"### RÀNG BUỘC ĐỊNH DẠNG (FE11): {json.dumps(formatting_constraints, ensure_ascii=False)}",
        ]

        if placeholder_mappings:
            prompt_parts.append(
                f"### ÁNH XẠ PLACEHOLDER -> AST: {json.dumps(placeholder_mappings, ensure_ascii=False)}"
            )

        prompt_parts.append(
            f"### DỮ LIỆU AST ĐÃ PHÂN TÍCH (MODULE 4.1):\n```json\n{json.dumps(ast_compact, ensure_ascii=False, indent=2)}\n```"
        )

        if include_gaps:
            gaps_compact = [g.model_dump() for g in coverage_report.gaps[:15]]
            prompt_parts.append(
                f"### BÁO CÁO ĐỘ PHỦ & LỖ HỔNG (MODULE 4.2 - Coverage {coverage_report.coverage_percentage}%):\n"
                f"```json\n{json.dumps(gaps_compact, ensure_ascii=False, indent=2)}\n```"
            )

        if custom_instructions:
            prompt_parts.append(f"### YÊU CẦU BỔ SUNG TỪ NGƯỜI DÙNG:\n{custom_instructions}")

        prompt_parts.append(
            "Hãy xuất trực tiếp nội dung tài liệu Markdown hoàn chỉnh theo đúng cấu trúc Template trên."
        )
        return system_prompt, "\n\n".join(prompt_parts)

    async def _try_call_llm(
        self,
        ai_config: AIParameterConfig,
        system_prompt: str,
        user_prompt: str,
        warnings: List[str],
    ) -> Optional[Tuple[str, str, str, int]]:
        provider = (ai_config.primary_provider or "openai").lower().strip()
        openai_key = os.getenv("OPENAI_API_KEY") or getattr(settings, "OPENAI_API_KEY", None)
        gemini_key = os.getenv("GEMINI_API_KEY") or getattr(settings, "GEMINI_API_KEY", None)

        if provider == "openai" and openai_key:
            for model in (ai_config.primary_model, ai_config.fallback_model):
                if not model or "gemini" in model.lower():
                    continue
                res = await self._call_openai(
                    api_key=openai_key,
                    model=model,
                    temperature=ai_config.temperature,
                    max_tokens=ai_config.max_output_tokens,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                )
                if res:
                    return res[0], "openai", model, res[1]
            warnings.append("Gọi OpenAI API không thành công; chuyển sang AST Template Engine cục bộ.")

        elif provider in ("gemini", "google") and gemini_key:
            model = ai_config.primary_model or "gemini-2.5-pro"
            res = await self._call_gemini(
                api_key=gemini_key,
                model=model,
                temperature=ai_config.temperature,
                max_tokens=ai_config.max_output_tokens,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
            )
            if res:
                return res[0], "gemini", model, res[1]
            warnings.append("Gọi Gemini API không thành công; chuyển sang AST Template Engine cục bộ.")
        else:
            warnings.append(
                f"Chưa cấu hình API Key cho provider '{provider}' trong môi trường; sử dụng AST Template Engine cục bộ."
            )

        return None

    async def _call_openai(
        self,
        api_key: str,
        model: str,
        temperature: float,
        max_tokens: int,
        system_prompt: str,
        user_prompt: str,
    ) -> Optional[Tuple[str, int]]:
        try:
            async with httpx.AsyncClient(timeout=45.0) as client:
                resp = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": model,
                        "temperature": temperature,
                        "max_tokens": max_tokens,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                    },
                )
            if resp.status_code != 200:
                return None
            data = resp.json()
            text = data["choices"][0]["message"]["content"]
            tokens = data.get("usage", {}).get("total_tokens", max(150, len(text) // 4))
            return text, tokens
        except Exception:
            return None

    async def _call_gemini(
        self,
        api_key: str,
        model: str,
        temperature: float,
        max_tokens: int,
        system_prompt: str,
        user_prompt: str,
    ) -> Optional[Tuple[str, int]]:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
            async with httpx.AsyncClient(timeout=45.0) as client:
                resp = await client.post(
                    url,
                    json={
                        "systemInstruction": {"parts": [{"text": system_prompt}]},
                        "contents": [{"parts": [{"text": user_prompt}]}],
                        "generationConfig": {
                            "temperature": temperature,
                            "maxOutputTokens": max_tokens,
                        },
                    },
                )
            if resp.status_code != 200:
                return None
            data = resp.json()
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            tokens = data.get("usageMetadata", {}).get("totalTokenCount", max(150, len(text) // 4))
            return text, tokens
        except Exception:
            return None

    def _render_deterministic_draft(
        self,
        ast_result: ASTParseResponse,
        coverage_report: CoverageReport,
        template_content: str,
        custom_instructions: Optional[str],
    ) -> str:
        classes = [e for e in ast_result.entities if e.entity_type == "class"]
        callables = [e for e in ast_result.entities if e.entity_type in ("function", "method")]

        if classes:
            class_lines = []
            for cls in classes:
                desc = cls.docstring or "_Chưa có mô tả docstring trong mã nguồn._"
                class_lines.append(
                    f"### `class {cls.name}` (Dòng {cls.start_line}–{cls.end_line})\n"
                    f"- **Mô tả:** {desc}\n"
                    f"- **Độ phức tạp tổng hợp:** `{cls.complexity_score}`\n"
                )
            classes_md = "\n".join(class_lines)
        else:
            classes_md = "_Module này không định nghĩa class nào (cấu trúc hướng hàm)._"

        if callables:
            func_lines = []
            for fn in callables:
                owner_prefix = f"{fn.parent_name}." if fn.parent_name else ""
                desc = fn.docstring or "_Cần bổ sung mô tả chức năng cho thực thể này._"
                func_lines.append(
                    f"### `{owner_prefix}{fn.name}` (Dòng {fn.start_line}–{fn.end_line})\n"
                    f"- **Chữ ký (Signature):** `{fn.signature}`\n"
                    f"- **Mô tả:** {desc}\n"
                    f"- **Kiểu trả về:** `{fn.return_type or 'Không khai báo'}` | **Độ phức tạp:** `{fn.complexity_score}`\n"
                )
                if fn.parameters:
                    func_lines.append("| Tham số | Kiểu dữ liệu | Giá trị mặc định |")
                    func_lines.append("| :--- | :--- | :--- |")
                    for p in fn.parameters:
                        func_lines.append(
                            f"| `{p.name}` | `{p.type_annotation or 'Any'}` | `{p.default_value or '-'}` |"
                        )
                    func_lines.append("")
            functions_md = "\n".join(func_lines)
        else:
            functions_md = "_Không phát hiện hàm hoặc phương thức nào trong tệp._"

        if coverage_report.gaps:
            gap_lines = [
                "| Mức độ | Thực thể | Dòng | Loại thiếu sót | Khuyến nghị |",
                "| :--- | :--- | :--- | :--- | :--- |",
            ]
            for g in coverage_report.gaps:
                full_name = f"{g.parent_name}.{g.entity_name}" if g.parent_name else g.entity_name
                gap_lines.append(
                    f"| **{g.severity.upper()}** | `{full_name}` | {g.start_line} | `{g.gap_type}` | {g.recommendation} |"
                )
            gaps_md = "\n".join(gap_lines)
        else:
            gaps_md = "Tất cả các thực thể mã nguồn đều đã đạt chuẩn tài liệu."

        rendered = template_content
        replacements = {
            "{{file_path}}": ast_result.file_path,
            "{{language}}": ast_result.language,
            "{{total_entities}}": str(ast_result.total_entities),
            "{{documented_entities}}": str(ast_result.documented_entities),
            "{{coverage_percentage}}": str(coverage_report.coverage_percentage),
            "{{classes_section}}": classes_md,
            "{{functions_section}}": functions_md,
            "{{gaps_section}}": gaps_md,
        }
        for key, val in replacements.items():
            rendered = rendered.replace(key, val)

        # Nếu dùng custom template từ FE11 không chứa các placeholder chuẩn, nối phần phân tích AST vào cuối
        if "{{functions_section}}" not in template_content:
            rendered += (
                f"\n\n---\n\n## Chi tiết Thực thể AST (`{ast_result.file_path}`)\n\n"
                f"{classes_md}\n\n{functions_md}\n\n"
                f"## Báo cáo Độ phủ Tài liệu ({coverage_report.coverage_percentage}%)\n\n{gaps_md}"
            )

        if custom_instructions:
            rendered += f"\n\n> **Ghi chú ngữ cảnh bổ sung:** {custom_instructions}\n"

        return rendered


ai_doc_generator_service = AIDocGeneratorService()