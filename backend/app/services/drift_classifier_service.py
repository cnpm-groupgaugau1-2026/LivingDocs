from __future__ import annotations

import ast
import difflib
import json
import os
import re
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from app.schemas.drift import (
    CodeFileInput,
    DriftCategory,
    DriftClassificationSummary,
    DriftClassifyRequest,
    DriftClassifyResponse,
    DriftItem,
)
from app.services.grounding_evidence_service import GroundingEvidenceEngine
from app.services.severity_scoring_service import SeverityScoringEngine


@dataclass
class ExtractedParam:
    name: str
    type_hint: Optional[str] = None
    default: Optional[str] = None


@dataclass
class CodeSymbol:
    name: str
    qualname: str
    kind: str
    file_path: str
    start_line: int
    end_line: int
    params: List[ExtractedParam] = field(default_factory=list)
    return_type: Optional[str] = None
    docstring: str = ""
    raised_exceptions: List[str] = field(default_factory=list)
    called_functions: List[str] = field(default_factory=list)
    returns_none_only: bool = False
    is_public: bool = True
    raw_snippet: str = ""


@dataclass
class DocSymbolRef:
    name: str
    raw_signature: Optional[str]
    params: List[ExtractedParam]
    return_type: Optional[str]
    description_block: str
    start_line: int
    end_line: int
    is_file_path: bool = False


class MultiCategoryDriftClassifier:
    """
    FE04 - 5.1, 5.2 & 5.3:
    1. Multi-Category Drift Classifier (Referential, Signature, Semantic)
    2. Severity Scoring Engine (Low, Medium, High, Critical)
    3. Grounding Evidence Extraction & Context Attachment Engine
    """

    _IGNORED_TOKENS = {
        "true", "false", "null", "none", "self", "cls", "args", "kwargs",
        "string", "str", "int", "float", "bool", "dict", "list", "any",
        "json", "http", "https", "get", "post", "put", "delete", "patch",
        "utf-8", "readme", "env", "api", "url", "id", "ok", "error",
    }

    def __init__(self) -> None:
        self.severity_engine = SeverityScoringEngine()
        self.grounding_engine = GroundingEvidenceEngine()

    def classify(self, request: DriftClassifyRequest) -> DriftClassifyResponse:
        warnings: List[str] = []
        code_symbols, known_paths = self._extract_all_code_symbols(request.code_files, warnings)
        doc_refs = self._extract_doc_references(request.markdown_content)

        symbol_by_name: Dict[str, List[CodeSymbol]] = {}
        for sym in code_symbols:
            symbol_by_name.setdefault(sym.name, []).append(sym)
            symbol_by_name.setdefault(sym.qualname, []).append(sym)

        drifts: List[DriftItem] = []
        matched_pairs: List[Tuple[DocSymbolRef, CodeSymbol]] = []

        # --------------------------------------------------------------
        # 1. REFERENTIAL DRIFT DETECTION (Sub-feature 5.1)
        # --------------------------------------------------------------
        for ref in doc_refs:
            if ref.is_file_path:
                normalized_ref = ref.name.replace("\\", "/").lstrip("./")
                if not any(p.endswith(normalized_ref) or normalized_ref.endswith(p) for p in known_paths):
                    closest_path = self._find_closest_match(normalized_ref, list(known_paths))
                    drifts.append(
                        DriftItem(
                            drift_id=f"drift-{uuid.uuid4().hex[:8]}",
                            category=DriftCategory.REFERENTIAL,
                            sub_type="broken_file_reference",
                            symbol_name=ref.name,
                            title=f"Đường dẫn tệp không tồn tại: `{ref.name}`",
                            description=(
                                f"Tài liệu tham chiếu đến tệp `{ref.name}` (dòng {ref.start_line}), "
                                "nhưng không tìm thấy tệp này trong mã nguồn."
                            ),
                            expected_in_doc=ref.name,
                            actual_in_code=closest_path or "Không tồn tại trong repository",
                            confidence=0.96,
                            suggestion=(
                                f"Cập nhật đường dẫn thành `{closest_path}`."
                                if closest_path
                                else f"Xóa tham chiếu tới `{ref.name}` hoặc bổ sung tệp tương ứng."
                            ),
                            doc_line_range=[ref.start_line, ref.end_line],
                        )
                    )
                continue

            matched = symbol_by_name.get(ref.name)
            if not matched:
                short_name = ref.name.split(".")[-1]
                matched = symbol_by_name.get(short_name)

            if not matched:
                all_names = [s.name for s in code_symbols if s.is_public]
                closest = self._find_closest_match(ref.name.split(".")[-1], all_names)
                drifts.append(
                    DriftItem(
                        drift_id=f"drift-{uuid.uuid4().hex[:8]}",
                        category=DriftCategory.REFERENTIAL,
                        sub_type="missing_or_renamed_symbol",
                        symbol_name=ref.name,
                        title=f"Ký hiệu không tồn tại trong mã nguồn: `{ref.name}`",
                        description=(
                            f"Tài liệu mô tả `{ref.name}` (dòng {ref.start_line}–{ref.end_line}) "
                            "nhưng hàm/lớp này đã bị xóa hoặc đổi tên."
                        ),
                        expected_in_doc=ref.raw_signature or ref.name,
                        actual_in_code=f"Có thể đã đổi tên thành `{closest}`" if closest else "Symbol not found",
                        confidence=0.94 if closest else 0.88,
                        suggestion=(
                            f"Kiểm tra xem `{ref.name}` đã được đổi tên thành `{closest}` hay chưa và cập nhật lại tài liệu."
                            if closest
                            else f"Xóa mục tài liệu của `{ref.name}` nếu chức năng này đã bị loại bỏ."
                        ),
                        doc_line_range=[ref.start_line, ref.end_line],
                    )
                )
            else:
                matched_pairs.append((ref, matched[0]))

        # --------------------------------------------------------------
        # 2. SIGNATURE DRIFT DETECTION (Sub-feature 5.1)
        # --------------------------------------------------------------
        for ref, sym in matched_pairs:
            drifts.extend(self._detect_signature_drifts(ref, sym))

        # --------------------------------------------------------------
        # 3. SEMANTIC DRIFT DETECTION (Sub-feature 5.1)
        # --------------------------------------------------------------
        analysis_mode: str = "ast_rule_engine"
        for ref, sym in matched_pairs:
            drifts.extend(self._detect_semantic_drifts_ast(ref, sym))

        if request.use_llm_semantic and matched_pairs:
            llm_drifts, used_llm = self._detect_semantic_drifts_llm(matched_pairs, warnings)
            if used_llm:
                analysis_mode = "ast_plus_llm_hybrid"
                drifts.extend(llm_drifts)

        # --------------------------------------------------------------
        # 4. SEVERITY SCORING ENGINE (Sub-feature 5.2)
        # --------------------------------------------------------------
        public_symbols = {s.qualname for s in code_symbols if s.is_public} | {
            s.name for s in code_symbols if s.is_public
        }
        mutating_symbols = {
            s.qualname
            for s in code_symbols
            if any(
                verb in call.lower()
                for call in s.called_functions
                for verb in ("delete", "remove", "drop", "commit", "save", "insert", "update", "write")
            )
        }
        scored_drifts, sev_counts, overall_score, overall_level = self.severity_engine.score_drifts(
            drifts=drifts,
            public_symbols=public_symbols,
            mutating_symbols=mutating_symbols,
        )

        # --------------------------------------------------------------
        # 5. GROUNDING EVIDENCE & CONTEXT ATTACHMENT (Sub-feature 5.3)
        # --------------------------------------------------------------
        grounded_drifts, grounded_count, dual_anchored_count = self.grounding_engine.attach_grounding_evidence(
            drifts=scored_drifts,
            doc_path=request.doc_path,
            markdown_content=request.markdown_content,
            code_files=request.code_files,
        )

        ref_count = sum(1 for d in grounded_drifts if d.category == DriftCategory.REFERENTIAL)
        sig_count = sum(1 for d in grounded_drifts if d.category == DriftCategory.SIGNATURE)
        sem_count = sum(1 for d in grounded_drifts if d.category == DriftCategory.SEMANTIC)

        summary = DriftClassificationSummary(
            total_drifts=len(grounded_drifts),
            referential_count=ref_count,
            signature_count=sig_count,
            semantic_count=sem_count,
            critical_count=sev_counts["critical"],
            high_count=sev_counts["high"],
            medium_count=sev_counts["medium"],
            low_count=sev_counts["low"],
            overall_risk_score=overall_score,
            overall_risk_level=overall_level,
            grounded_drifts_count=grounded_count,
            dual_anchored_count=dual_anchored_count,
            analyzed_symbols=len(code_symbols),
            documented_symbols=len(doc_refs),
            analysis_mode=analysis_mode,  # type: ignore[arg-type]
        )

        return DriftClassifyResponse(
            doc_path=request.doc_path,
            summary=summary,
            drifts=grounded_drifts,
            warnings=warnings,
        )

    # ------------------------------------------------------------------
    # EXTRACTORS: CODE (AST) & MARKDOWN
    # ------------------------------------------------------------------
    def _extract_all_code_symbols(
        self, code_files: List[CodeFileInput], warnings: List[str]
    ) -> Tuple[List[CodeSymbol], set[str]]:
        all_symbols: List[CodeSymbol] = []
        known_paths: set[str] = set()

        for f in code_files:
            norm_path = f.file_path.replace("\\", "/").lstrip("./")
            known_paths.add(norm_path)
            lang = (f.language or self._infer_language(norm_path)).lower()

            if lang == "python":
                all_symbols.extend(self._parse_python_ast(norm_path, f.content, warnings))
            else:
                all_symbols.extend(self._parse_ts_js_regex(norm_path, f.content))

        return all_symbols, known_paths

    def _infer_language(self, file_path: str) -> str:
        ext = os.path.splitext(file_path)[1].lower()
        mapping = {
            ".py": "python",
            ".ts": "typescript",
            ".tsx": "tsx",
            ".js": "javascript",
            ".jsx": "jsx",
        }
        return mapping.get(ext, "unknown")

    def _parse_python_ast(
        self, file_path: str, source: str, warnings: List[str]
    ) -> List[CodeSymbol]:
        symbols: List[CodeSymbol] = []
        try:
            tree = ast.parse(source)
        except SyntaxError as exc:
            warnings.append(f"Không thể parse AST Python tại `{file_path}` dòng {exc.lineno}: {exc.msg}")
            return symbols

        lines = source.splitlines()

        class Visitor(ast.NodeVisitor):
            def __init__(self) -> None:
                self.current_class: Optional[str] = None

            def visit_ClassDef(self, node: ast.ClassDef) -> None:
                end_line = getattr(node, "end_lineno", node.lineno)
                snippet = "\n".join(lines[node.lineno - 1 : end_line])
                symbols.append(
                    CodeSymbol(
                        name=node.name,
                        qualname=node.name,
                        kind="class",
                        file_path=file_path,
                        start_line=node.lineno,
                        end_line=end_line,
                        docstring=ast.get_docstring(node) or "",
                        is_public=not node.name.startswith("_"),
                        raw_snippet=snippet,
                    )
                )
                prev = self.current_class
                self.current_class = node.name
                self.generic_visit(node)
                self.current_class = prev

            def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
                self._handle_func(node, is_async=False)

            def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
                self._handle_func(node, is_async=True)

            def _handle_func(self, node: ast.FunctionDef | ast.AsyncFunctionDef, is_async: bool) -> None:
                end_line = getattr(node, "end_lineno", node.lineno)
                snippet = "\n".join(lines[node.lineno - 1 : end_line])

                params: List[ExtractedParam] = []
                all_args = list(node.args.posonlyargs) + list(node.args.args)
                defaults = [None] * (len(all_args) - len(node.args.defaults)) + list(node.args.defaults)

                for arg, default_node in zip(all_args, defaults):
                    if arg.arg in {"self", "cls"}:
                        continue
                    type_hint = ast.unparse(arg.annotation) if arg.annotation else None
                    default_val = ast.unparse(default_node) if default_node is not None else None
                    params.append(ExtractedParam(name=arg.arg, type_hint=type_hint, default=default_val))

                for kw_arg, kw_default in zip(node.args.kwonlyargs, node.args.kw_defaults):
                    type_hint = ast.unparse(kw_arg.annotation) if kw_arg.annotation else None
                    default_val = ast.unparse(kw_default) if kw_default is not None else None
                    params.append(ExtractedParam(name=kw_arg.arg, type_hint=type_hint, default=default_val))

                return_type = ast.unparse(node.returns) if node.returns else None

                raised: List[str] = []
                called: List[str] = []
                has_non_none_return = False

                for child in ast.walk(node):
                    if isinstance(child, ast.Raise) and child.exc is not None:
                        if isinstance(child.exc, ast.Call):
                            raised.append(ast.unparse(child.exc.func))
                        else:
                            raised.append(ast.unparse(child.exc))
                    elif isinstance(child, ast.Call):
                        called.append(ast.unparse(child.func))
                    elif isinstance(child, ast.Return):
                        if child.value is not None and not (
                            isinstance(child.value, ast.Constant) and child.value.value is None
                        ):
                            has_non_none_return = True

                qualname = f"{self.current_class}.{node.name}" if self.current_class else node.name
                kind = "method" if self.current_class else ("async_function" if is_async else "function")

                symbols.append(
                    CodeSymbol(
                        name=node.name,
                        qualname=qualname,
                        kind=kind,
                        file_path=file_path,
                        start_line=node.lineno,
                        end_line=end_line,
                        params=params,
                        return_type=return_type,
                        docstring=ast.get_docstring(node) or "",
                        raised_exceptions=sorted(set(raised)),
                        called_functions=sorted(set(called)),
                        returns_none_only=not has_non_none_return,
                        is_public=not node.name.startswith("_"),
                        raw_snippet=snippet,
                    )
                )

        Visitor().visit(tree)
        return symbols

    def _parse_ts_js_regex(self, file_path: str, source: str) -> List[CodeSymbol]:
        symbols: List[CodeSymbol] = []
        lines = source.splitlines()
        pattern = re.compile(
            r"^(?:export\s+)?(?:async\s+)?function\s+([A-Za-z_]\w*)\s*\(([^)]*)\)\s*(?::\s*([^{]+))?\s*\{"
        )
        for idx, line in enumerate(lines, start=1):
            m = pattern.match(line.strip())
            if not m:
                continue
            name, raw_params, ret_type = m.group(1), m.group(2).strip(), (m.group(3) or "").strip() or None
            params = self._parse_param_list_string(raw_params)
            snippet = "\n".join(lines[idx - 1 : min(len(lines), idx + 25)])
            symbols.append(
                CodeSymbol(
                    name=name,
                    qualname=name,
                    kind="function",
                    file_path=file_path,
                    start_line=idx,
                    end_line=min(len(lines), idx + 25),
                    params=params,
                    return_type=ret_type,
                    raw_snippet=snippet,
                )
            )
        return symbols

    def _extract_doc_references(self, markdown: str) -> List[DocSymbolRef]:
        lines = markdown.splitlines()
        refs: List[DocSymbolRef] = []
        seen_names: set[str] = set()

        heading_pattern = re.compile(
            r"^#{1,4}\s+(?:"
            r"`([A-Za-z_][\w.]*)(?:\(([^)]*)\))?(?:\s*->\s*([^\s`]+))?`"
            r"|([A-Za-z_][\w.]*)\(([^)]*)\)(?:\s*->\s*(\S+))?"
            r"|([a-z_][a-z0-9_]*|[A-Z][a-z0-9]+(?:[A-Z][A-Za-z0-9_]*)+)"
            r")\s*$"
        )
        inline_call_pattern = re.compile(r"`([A-Za-z_][\w.]*)\(([^)]*)\)(?:\s*->\s*([^`]+))?`")
        file_path_pattern = re.compile(r"`((?:[\w.-]+/)+[\w.-]+\.(?:py|ts|tsx|js|jsx|sql|json|yaml|yml|md))`")

        for idx, line in enumerate(lines, start=1):
            block_end = min(len(lines), idx + 12)
            desc_block = "\n".join(lines[idx - 1 : block_end])

            for fp_match in file_path_pattern.finditer(line):
                fp = fp_match.group(1)
                if fp not in seen_names:
                    seen_names.add(fp)
                    refs.append(
                        DocSymbolRef(
                            name=fp,
                            raw_signature=fp,
                            params=[],
                            return_type=None,
                            description_block=desc_block,
                            start_line=idx,
                            end_line=idx,
                            is_file_path=True,
                        )
                    )

            h_match = heading_pattern.match(line.strip())
            if h_match:
                sym_name = h_match.group(1) or h_match.group(4) or h_match.group(7)
                raw_params = h_match.group(2) if h_match.group(1) else h_match.group(5)
                ret_type = h_match.group(3) if h_match.group(1) else h_match.group(6)
                if sym_name and sym_name.lower() not in self._IGNORED_TOKENS and sym_name not in seen_names:
                    seen_names.add(sym_name)
                    params = self._parse_param_list_string(raw_params) if raw_params is not None else []
                    if not params:
                        params = self._extract_documented_params_from_block(lines[idx : min(len(lines), idx + 15)])
                    refs.append(
                        DocSymbolRef(
                            name=sym_name,
                            raw_signature=line.strip(),
                            params=params,
                            return_type=ret_type,
                            description_block=desc_block,
                            start_line=idx,
                            end_line=block_end,
                        )
                    )
                continue

            for c_match in inline_call_pattern.finditer(line):
                sym_name = c_match.group(1)
                if sym_name.lower() in self._IGNORED_TOKENS or sym_name in seen_names:
                    continue
                seen_names.add(sym_name)
                raw_params = c_match.group(2)
                ret_type = c_match.group(3).strip() if c_match.group(3) else None
                params = self._parse_param_list_string(raw_params)
                refs.append(
                    DocSymbolRef(
                        name=sym_name,
                        raw_signature=c_match.group(0),
                        params=params,
                        return_type=ret_type,
                        description_block=desc_block,
                        start_line=idx,
                        end_line=block_end,
                    )
                )

        return refs

    def _parse_param_list_string(self, raw: Optional[str]) -> List[ExtractedParam]:
        if not raw or not raw.strip():
            return []
        params: List[ExtractedParam] = []
        for part in raw.split(","):
            token = part.strip()
            if not token or token in {"self", "cls", "*args", "**kwargs", "..."}:
                continue
            default_val: Optional[str] = None
            type_hint: Optional[str] = None

            if "=" in token:
                left, default_val = token.split("=", 1)
                token = left.strip()
                default_val = default_val.strip()

            if ":" in token:
                name_part, type_part = token.split(":", 1)
                name = name_part.strip().lstrip("*")
                type_hint = type_part.strip()
            else:
                name = token.lstrip("*").rstrip("?")

            if name:
                params.append(ExtractedParam(name=name, type_hint=type_hint, default=default_val))
        return params

    def _extract_documented_params_from_block(self, block_lines: List[str]) -> List[ExtractedParam]:
        params: List[ExtractedParam] = []
        bullet_re = re.compile(r"^[-*]\s+`([A-Za-z_]\w*)`(?:\s*\(([^)]+)\))?\s*:")
        for line in block_lines:
            if line.startswith("#"):
                break
            m = bullet_re.match(line.strip())
            if m:
                params.append(ExtractedParam(name=m.group(1), type_hint=m.group(2)))
        return params

    # ------------------------------------------------------------------
    # CATEGORY 2: SIGNATURE DRIFT
    # ------------------------------------------------------------------
    def _detect_signature_drifts(self, ref: DocSymbolRef, sym: CodeSymbol) -> List[DriftItem]:
        drifts: List[DriftItem] = []
        if sym.kind == "class":
            return drifts

        has_explicit_call = ref.raw_signature and "(" in ref.raw_signature
        if has_explicit_call or ref.params:
            doc_param_names = [p.name for p in ref.params]
            code_param_names = [p.name for p in sym.params]

            missing_in_doc = [p for p in sym.params if p.name not in doc_param_names]
            extra_in_doc = [p for p in ref.params if p.name not in code_param_names]

            if missing_in_doc or extra_in_doc:
                required_new = [p.name for p in missing_in_doc if p.default is None]
                detail_parts: List[str] = []
                if missing_in_doc:
                    detail_parts.append(
                        f"Mã nguồn có thêm tham số: {', '.join(f'`{p.name}`' for p in missing_in_doc)}"
                    )
                if extra_in_doc:
                    detail_parts.append(
                        f"Tài liệu ghi thừa tham số đã xóa: {', '.join(f'`{p.name}`' for p in extra_in_doc)}"
                    )

                drifts.append(
                    DriftItem(
                        drift_id=f"drift-{uuid.uuid4().hex[:8]}",
                        category=DriftCategory.SIGNATURE,
                        sub_type="breaking_param_change" if (required_new or extra_in_doc) else "optional_param_added",
                        symbol_name=sym.qualname,
                        file_path=sym.file_path,
                        title=f"Sai lệch danh sách tham số của `{sym.qualname}`",
                        description=". ".join(detail_parts) + ".",
                        expected_in_doc=f"{sym.name}({', '.join(doc_param_names)})",
                        actual_in_code=self._format_code_signature(sym),
                        confidence=0.97,
                        suggestion=f"Cập nhật chữ ký trong tài liệu thành `{self._format_code_signature(sym)}`.",
                        doc_line_range=[ref.start_line, ref.end_line],
                        code_line_range=[sym.start_line, sym.end_line],
                    )
                )
            elif doc_param_names != code_param_names:
                drifts.append(
                    DriftItem(
                        drift_id=f"drift-{uuid.uuid4().hex[:8]}",
                        category=DriftCategory.SIGNATURE,
                        sub_type="param_order_mismatch",
                        symbol_name=sym.qualname,
                        file_path=sym.file_path,
                        title=f"Sai thứ tự tham số của `{sym.qualname}`",
                        description=(
                            f"Thứ tự tham số trong tài liệu ({', '.join(doc_param_names)}) "
                            f"không khớp với mã nguồn ({', '.join(code_param_names)})."
                        ),
                        expected_in_doc=f"{sym.name}({', '.join(doc_param_names)})",
                        actual_in_code=self._format_code_signature(sym),
                        confidence=0.95,
                        suggestion=f"Sắp xếp lại tham số theo đúng thứ tự: `{self._format_code_signature(sym)}`.",
                        doc_line_range=[ref.start_line, ref.end_line],
                        code_line_range=[sym.start_line, sym.end_line],
                    )
                )

            code_param_map = {p.name: p for p in sym.params}
            for dp in ref.params:
                cp = code_param_map.get(dp.name)
                if not cp:
                    continue
                if dp.type_hint and cp.type_hint and self._norm_type(dp.type_hint) != self._norm_type(cp.type_hint):
                    drifts.append(
                        DriftItem(
                            drift_id=f"drift-{uuid.uuid4().hex[:8]}",
                            category=DriftCategory.SIGNATURE,
                            sub_type="param_type_mismatch",
                            symbol_name=sym.qualname,
                            file_path=sym.file_path,
                            title=f"Sai kiểu dữ liệu tham số `{dp.name}` trong `{sym.qualname}`",
                            description=(
                                f"Tham số `{dp.name}` được mô tả kiểu `{dp.type_hint}` "
                                f"nhưng mã nguồn định nghĩa kiểu `{cp.type_hint}`."
                            ),
                            expected_in_doc=f"{dp.name}: {dp.type_hint}",
                            actual_in_code=f"{cp.name}: {cp.type_hint}",
                            confidence=0.93,
                            suggestion=f"Đổi kiểu dữ liệu của `{dp.name}` trong tài liệu thành `{cp.type_hint}`.",
                            doc_line_range=[ref.start_line, ref.end_line],
                            code_line_range=[sym.start_line, sym.end_line],
                        )
                    )
                if dp.default is not None and cp.default is not None and dp.default != cp.default:
                    drifts.append(
                        DriftItem(
                            drift_id=f"drift-{uuid.uuid4().hex[:8]}",
                            category=DriftCategory.SIGNATURE,
                            sub_type="default_value_mismatch",
                            symbol_name=sym.qualname,
                            file_path=sym.file_path,
                            title=f"Sai giá trị mặc định của `{dp.name}` trong `{sym.qualname}`",
                            description=(
                                f"Giá trị mặc định của `{dp.name}` trong tài liệu là `{dp.default}`, "
                                f"nhưng trong mã nguồn là `{cp.default}`."
                            ),
                            expected_in_doc=f"{dp.name}={dp.default}",
                            actual_in_code=f"{cp.name}={cp.default}",
                            confidence=0.95,
                            suggestion=f"Cập nhật giá trị mặc định của `{dp.name}` thành `{cp.default}`.",
                            doc_line_range=[ref.start_line, ref.end_line],
                            code_line_range=[sym.start_line, sym.end_line],
                        )
                    )

        if ref.return_type and sym.return_type:
            if self._norm_type(ref.return_type) != self._norm_type(sym.return_type):
                drifts.append(
                    DriftItem(
                        drift_id=f"drift-{uuid.uuid4().hex[:8]}",
                        category=DriftCategory.SIGNATURE,
                        sub_type="return_type_mismatch",
                        symbol_name=sym.qualname,
                        file_path=sym.file_path,
                        title=f"Sai kiểu trả về của `{sym.qualname}`",
                        description=(
                            f"Tài liệu ghi kiểu trả về là `{ref.return_type}` "
                            f"nhưng mã nguồn trả về `{sym.return_type}`."
                        ),
                        expected_in_doc=f"-> {ref.return_type}",
                        actual_in_code=f"-> {sym.return_type}",
                        confidence=0.94,
                        suggestion=f"Cập nhật kiểu trả về trong tài liệu thành `{sym.return_type}`.",
                        doc_line_range=[ref.start_line, ref.end_line],
                        code_line_range=[sym.start_line, sym.end_line],
                    )
                )

        return drifts

    # ------------------------------------------------------------------
    # CATEGORY 3: SEMANTIC DRIFT
    # ------------------------------------------------------------------
    def _detect_semantic_drifts_ast(self, ref: DocSymbolRef, sym: CodeSymbol) -> List[DriftItem]:
        drifts: List[DriftItem] = []
        doc_lower = ref.description_block.lower()

        if sym.raised_exceptions:
            undocumented_excs = [
                exc for exc in sym.raised_exceptions
                if exc.split(".")[-1].lower() not in doc_lower
            ]
            if undocumented_excs and not any(
                k in doc_lower for k in ("raise", "raises", "exception", "error", "lỗi", "ngoại lệ")
            ):
                drifts.append(
                    DriftItem(
                        drift_id=f"drift-{uuid.uuid4().hex[:8]}",
                        category=DriftCategory.SEMANTIC,
                        sub_type="undocumented_exception",
                        symbol_name=sym.qualname,
                        file_path=sym.file_path,
                        title=f"Thiếu mô tả ngoại lệ trong `{sym.qualname}`",
                        description=(
                            f"Hàm `{sym.qualname}` ném ngoại lệ `{', '.join(undocumented_excs)}` trong mã nguồn "
                            "nhưng tài liệu không đề cập đến các tình huống lỗi này."
                        ),
                        expected_in_doc="Không mô tả ngoại lệ/lỗi trả về",
                        actual_in_code=f"Raises: {', '.join(undocumented_excs)}",
                        confidence=0.87,
                        suggestion=f"Bổ sung mục mô tả ngoại lệ `{', '.join(undocumented_excs)}` và điều kiện kích hoạt.",
                        doc_line_range=[ref.start_line, ref.end_line],
                        code_line_range=[sym.start_line, sym.end_line],
                    )
                )

        if any(k in doc_lower for k in ("read-only", "readonly", "chỉ đọc", "không thay đổi dữ liệu", "idempotent")):
            mutating_calls = [
                c for c in sym.called_functions
                if any(
                    verb in c.lower()
                    for verb in ("delete", "remove", "drop", "commit", "save", "insert", "update", "write")
                )
            ]
            if mutating_calls:
                drifts.append(
                    DriftItem(
                        drift_id=f"drift-{uuid.uuid4().hex[:8]}",
                        category=DriftCategory.SEMANTIC,
                        sub_type="side_effect_contradiction",
                        symbol_name=sym.qualname,
                        file_path=sym.file_path,
                        title=f"Mâu thuẫn hành vi read-only tại `{sym.qualname}`",
                        description=(
                            f"Tài liệu mô tả `{sym.qualname}` là chỉ đọc (read-only), "
                            f"nhưng mã nguồn thực thi thao tác thay đổi trạng thái: `{', '.join(mutating_calls)}`."
                        ),
                        expected_in_doc="Hành vi chỉ đọc (không phát sinh side-effect)",
                        actual_in_code=f"Gọi hàm tác động dữ liệu: {', '.join(mutating_calls)}",
                        confidence=0.91,
                        suggestion="Cập nhật mô tả nêu rõ tác động ghi/xóa dữ liệu của hàm này.",
                        doc_line_range=[ref.start_line, ref.end_line],
                        code_line_range=[sym.start_line, sym.end_line],
                    )
                )

        if sym.returns_none_only and any(
            k in doc_lower
            for k in (
                "returns a ",
                "returns the ",
                "trả về danh sách",
                "trả về đối tượng",
                "trả về kết quả",
                "trả về chuỗi",
            )
        ):
            drifts.append(
                DriftItem(
                    drift_id=f"drift-{uuid.uuid4().hex[:8]}",
                    category=DriftCategory.SEMANTIC,
                    sub_type="return_behavior_mismatch",
                    symbol_name=sym.qualname,
                    file_path=sym.file_path,
                    title=f"Mâu thuẫn giá trị trả về của `{sym.qualname}`",
                    description=(
                        f"Tài liệu mô tả `{sym.qualname}` trả về dữ liệu cụ thể, "
                        "nhưng hàm trong mã nguồn không trả về giá trị (luôn trả về `None`)."
                    ),
                    expected_in_doc="Hàm trả về dữ liệu/kết quả",
                    actual_in_code="Hàm trả về None (void)",
                    confidence=0.89,
                    suggestion="Chỉnh lại mô tả hành vi trả về hoặc bổ sung câu lệnh `return` trong mã nguồn.",
                    doc_line_range=[ref.start_line, ref.end_line],
                    code_line_range=[sym.start_line, sym.end_line],
                )
            )

        return drifts

    def _detect_semantic_drifts_llm(
        self,
        matched_pairs: List[Tuple[DocSymbolRef, CodeSymbol]],
        warnings: List[str],
    ) -> Tuple[List[DriftItem], bool]:
        api_key = os.getenv("GEMINI_API_KEY", "").strip()
        if not api_key:
            warnings.append("Chưa cấu hình GEMINI_API_KEY nên bỏ qua bước kiểm tra Hybrid LLM Semantic.")
            return [], False

        try:
            import google.generativeai as genai  # type: ignore[import-untyped]
        except Exception:
            warnings.append("Thư viện google-generativeai chưa được cài đặt; sử dụng AST Rule Engine.")
            return [], False

        try:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel("gemini-2.5-flash")
            drifts: List[DriftItem] = []

            for ref, sym in matched_pairs[:5]:
                prompt = (
                    "Compare the following Markdown documentation against the actual Python/TS implementation.\n"
                    "Return ONLY a JSON array of semantic behavioral contradictions (empty array [] if aligned).\n"
                    "Each item must have keys: title, description, expected_in_doc, actual_in_code, suggestion.\n\n"
                    f"DOCUMENTATION:\n{ref.description_block}\n\n"
                    f"CODE ({sym.file_path}):\n{sym.raw_snippet}\n"
                )
                resp = model.generate_content(prompt)
                raw_text = (resp.text or "").strip()
                json_match = re.search(r"\[.*\]", raw_text, re.DOTALL)
                if not json_match:
                    continue
                items = json.loads(json_match.group(0))
                if not isinstance(items, list):
                    continue
                for entry in items:
                    if not isinstance(entry, dict) or not entry.get("title"):
                        continue
                    drifts.append(
                        DriftItem(
                            drift_id=f"drift-{uuid.uuid4().hex[:8]}",
                            category=DriftCategory.SEMANTIC,
                            sub_type="llm_behavioral_contradiction",
                            symbol_name=sym.qualname,
                            file_path=sym.file_path,
                            title=str(entry.get("title")),
                            description=str(entry.get("description", "")),
                            expected_in_doc=str(entry.get("expected_in_doc", "")),
                            actual_in_code=str(entry.get("actual_in_code", "")),
                            confidence=0.84,
                            suggestion=str(entry.get("suggestion", "")),
                            doc_line_range=[ref.start_line, ref.end_line],
                            code_line_range=[sym.start_line, sym.end_line],
                        )
                    )
            return drifts, True
        except Exception as exc:
            warnings.append(f"Hybrid LLM Semantic fallback sang AST Rule Engine do lỗi: {exc}")
            return [], False

    # ------------------------------------------------------------------
    # HELPERS
    # ------------------------------------------------------------------
    def _format_code_signature(self, sym: CodeSymbol) -> str:
        parts: List[str] = []
        for p in sym.params:
            segment = p.name
            if p.type_hint:
                segment += f": {p.type_hint}"
            if p.default is not None:
                segment += f" = {p.default}"
            parts.append(segment)
        ret = f" -> {sym.return_type}" if sym.return_type else ""
        return f"{sym.name}({', '.join(parts)}){ret}"

    def _norm_type(self, type_str: str) -> str:
        cleaned = re.sub(r"\s+", "", type_str).lower()
        aliases = {
            "boolean": "bool",
            "integer": "int",
            "string": "str",
            "number": "float",
            "object": "dict",
            "array": "list",
        }
        return aliases.get(cleaned, cleaned)

    def _find_closest_match(self, target: str, candidates: List[str]) -> Optional[str]:
        matches = difflib.get_close_matches(target, candidates, n=1, cutoff=0.6)
        return matches[0] if matches else None