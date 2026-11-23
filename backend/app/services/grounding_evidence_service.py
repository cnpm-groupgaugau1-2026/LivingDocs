from __future__ import annotations

import ast
import difflib
import os
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from app.schemas.drift import (
    CodeFileInput,
    DriftCategory,
    DriftItem,
    EvidenceLine,
    EvidenceSourceBlock,
    GroundingContextAttachment,
)


@dataclass
class _AstNodeEvidence:
    name: str
    qualname: str
    kind: str
    file_path: str
    start_line: int
    end_line: int
    signature_end_line: int
    signature_text: str
    return_type: Optional[str]
    raise_lines: List[Tuple[int, str, str]] = field(default_factory=list)
    mutating_call_lines: List[Tuple[int, str, str]] = field(default_factory=list)
    return_lines: List[Tuple[int, str]] = field(default_factory=list)


class GroundingEvidenceEngine:
    """
    FE04 - 5.3: Grounding Evidence Extraction & Context Attachment Engine
    Trích xuất bằng chứng dòng lệnh chính xác từ Markdown & AST, đính kèm
    cửa sổ ngữ cảnh xung quanh và đóng gói payload chống ảo giác cho AI repair.
    """

    _MUTATING_VERBS = (
        "delete",
        "remove",
        "drop",
        "commit",
        "save",
        "insert",
        "update",
        "write",
    )

    def attach_grounding_evidence(
        self,
        drifts: List[DriftItem],
        doc_path: str,
        markdown_content: str,
        code_files: List[CodeFileInput],
    ) -> Tuple[List[DriftItem], int, int]:
        if not drifts:
            return [], 0, 0

        doc_lines = markdown_content.splitlines()
        code_lines_by_file: Dict[str, List[str]] = {}
        ast_nodes_by_symbol: Dict[str, _AstNodeEvidence] = {}
        all_ast_nodes: List[_AstNodeEvidence] = []

        for cf in code_files:
            norm_path = cf.file_path.replace("\\", "/").lstrip("./")
            lines = cf.content.splitlines()
            code_lines_by_file[norm_path] = lines

            ext = os.path.splitext(norm_path)[1].lower()
            if (cf.language or "").lower() == "python" or ext == ".py":
                extracted = self._extract_python_node_evidences(norm_path, cf.content, lines)
                for item in extracted:
                    ast_nodes_by_symbol[item.qualname] = item
                    ast_nodes_by_symbol.setdefault(item.name, item)
                    all_ast_nodes.append(item)

        related_symbols = sorted({n.qualname for n in all_ast_nodes})
        enriched_drifts: List[DriftItem] = []
        dual_anchored_count = 0

        for drift in drifts:
            doc_evidence = self._build_doc_evidence(
                doc_path=doc_path,
                doc_lines=doc_lines,
                line_range=drift.doc_line_range,
                annotation=f"[{drift.category.upper()}] {drift.title}",
            )

            ast_node = self._resolve_ast_node(drift, ast_nodes_by_symbol)
            candidate_node: Optional[_AstNodeEvidence] = None

            if not ast_node and drift.category == DriftCategory.REFERENTIAL and drift.sub_type != "broken_file_reference":
                short_target = drift.symbol_name.split(".")[-1]
                matches = difflib.get_close_matches(short_target, list(ast_nodes_by_symbol.keys()), n=1, cutoff=0.6)
                if matches:
                    candidate_node = ast_nodes_by_symbol[matches[0]]

            target_node = ast_node or candidate_node
            code_evidence: Optional[EvidenceSourceBlock] = None
            ast_facts: List[str] = []

            if target_node:
                c_lines = code_lines_by_file.get(target_node.file_path, [])
                pinpoint_lines, node_proof, ast_facts = self._inspect_pinpoint_ast_lines(drift, target_node)
                code_evidence = self._build_code_evidence(
                    ast_node=target_node,
                    code_lines=c_lines,
                    pinpoint_lines=pinpoint_lines,
                    node_proof=node_proof,
                    is_candidate=(candidate_node is not None),
                )
            else:
                ast_facts = [
                    f"Không tìm thấy `{drift.symbol_name}` trong {len(code_lines_by_file)} tệp mã nguồn được phân tích.",
                    f"Các ký hiệu hợp lệ hiện có trong mã nguồn: {', '.join(related_symbols) if related_symbols else 'Không có'}.",
                ]

            if ast_node is not None:
                grounding_status = "verified_dual_anchor"
                dual_anchored_count += 1
            elif candidate_node is not None:
                grounding_status = "candidate_match_found"
            else:
                grounding_status = "doc_only_missing_target"

            ai_payload = self._build_ai_grounding_payload(
                drift=drift,
                grounding_status=grounding_status,
                doc_evidence=doc_evidence,
                code_evidence=code_evidence,
                ast_facts=ast_facts,
                related_symbols=related_symbols,
            )

            attachment = GroundingContextAttachment(
                evidence_id=f"ev-{uuid.uuid4().hex[:8]}",
                grounding_status=grounding_status,  # type: ignore[arg-type]
                doc_evidence=doc_evidence,
                code_evidence=code_evidence,
                ast_facts=ast_facts,
                related_symbols=related_symbols,
                ai_grounding_payload=ai_payload,
            )

            enriched_drifts.append(drift.model_copy(update={"grounding": attachment}))

        return enriched_drifts, len(enriched_drifts), dual_anchored_count

    def _resolve_ast_node(
        self, drift: DriftItem, ast_nodes_by_symbol: Dict[str, _AstNodeEvidence]
    ) -> Optional[_AstNodeEvidence]:
        if drift.category == DriftCategory.REFERENTIAL:
            return None
        node = ast_nodes_by_symbol.get(drift.symbol_name)
        if not node:
            node = ast_nodes_by_symbol.get(drift.symbol_name.split(".")[-1])
        return node

    def _inspect_pinpoint_ast_lines(
        self, drift: DriftItem, node: _AstNodeEvidence
    ) -> Tuple[Dict[int, str], str, List[str]]:
        pinpoint: Dict[int, str] = {}
        facts: List[str] = [
            f"Chữ ký AST thực tế ({node.file_path}:{node.start_line}): `{node.signature_text}`",
        ]

        if node.raise_lines:
            exc_summary = ", ".join(f"{exc} (L{ln})" for ln, exc, _ in node.raise_lines)
            facts.append(f"Ngoại lệ trong thân hàm AST: {exc_summary}")
        if node.mutating_call_lines:
            call_summary = ", ".join(f"{fn} (L{ln})" for ln, fn, _ in node.mutating_call_lines)
            facts.append(f"Thao tác thay đổi dữ liệu AST: {call_summary}")
        if node.return_lines:
            ret_summary = ", ".join(f"`{stmt}` (L{ln})" for ln, stmt in node.return_lines)
            facts.append(f"Câu lệnh trả về AST: {ret_summary}")
        else:
            facts.append("Hàm không có câu lệnh return trả về giá trị (luôn trả về None).")

        # Xác định dòng AST chính xác nhất gây ra lỗi hiện tại
        if drift.sub_type == "undocumented_exception" and node.raise_lines:
            for ln, exc, _ in node.raise_lines:
                pinpoint[ln] = f"AST Raise: ném ngoại lệ `{exc}` chưa mô tả trong tài liệu"
            first_ln, first_exc, _ = node.raise_lines[0]
            proof = f"ast.Raise(exc='{first_exc}', lineno={first_ln}) inside {node.qualname}"
        elif drift.sub_type == "side_effect_contradiction" and node.mutating_call_lines:
            for ln, fn, _ in node.mutating_call_lines:
                pinpoint[ln] = f"AST Call: gọi `{fn}` gây thay đổi trạng thái dữ liệu"
            first_ln, first_fn, _ = node.mutating_call_lines[0]
            proof = f"ast.Call(func='{first_fn}', lineno={first_ln}) inside {node.qualname}"
        elif drift.sub_type == "return_behavior_mismatch":
            for ln in range(node.start_line, node.signature_end_line + 1):
                pinpoint[ln] = "AST Definition: thân hàm không trả về dữ liệu (void/None)"
            proof = f"ast.FunctionDef(name='{node.qualname}', lineno={node.start_line}, returns_none_only=True)"
        else:
            for ln in range(node.start_line, node.signature_end_line + 1):
                pinpoint[ln] = "AST Signature: chữ ký hàm thực tế trong mã nguồn"
            proof = (
                f"ast.FunctionDef(name='{node.qualname}', lineno={node.start_line}, "
                f"returns={node.return_type!r})"
            )

        return pinpoint, proof, facts

    def _build_doc_evidence(
        self,
        doc_path: str,
        doc_lines: List[str],
        line_range: Optional[List[int]],
        annotation: str,
    ) -> EvidenceSourceBlock:
        if not doc_lines:
            return EvidenceSourceBlock(
                source_type="markdown_doc",
                file_path=doc_path,
                exact_quote="",
            )

        start = max(1, line_range[0]) if line_range and len(line_range) >= 2 else 1
        end = min(len(doc_lines), line_range[1]) if line_range and len(line_range) >= 2 else min(len(doc_lines), 3)

        win_start = max(1, start - 1)
        win_end = min(len(doc_lines), end + 1)

        context_lines: List[EvidenceLine] = []
        for ln in range(win_start, win_end + 1):
            is_target = start <= ln <= end
            context_lines.append(
                EvidenceLine(
                    line_number=ln,
                    content=doc_lines[ln - 1],
                    is_target=is_target,
                    annotation=annotation if (is_target and ln == start) else None,
                )
            )

        exact_quote = "\n".join(doc_lines[start - 1 : end])
        return EvidenceSourceBlock(
            source_type="markdown_doc",
            file_path=doc_path,
            start_line=start,
            end_line=end,
            exact_quote=exact_quote,
            context_lines=context_lines,
        )

    def _build_code_evidence(
        self,
        ast_node: _AstNodeEvidence,
        code_lines: List[str],
        pinpoint_lines: Dict[int, str],
        node_proof: str,
        is_candidate: bool,
    ) -> EvidenceSourceBlock:
        start = max(1, ast_node.start_line)
        end = min(len(code_lines), ast_node.end_line)
        win_start = max(1, start - 1)
        win_end = min(len(code_lines), end + 1)

        context_lines: List[EvidenceLine] = []
        for ln in range(win_start, win_end + 1):
            is_target = ln in pinpoint_lines
            note = pinpoint_lines.get(ln)
            if is_candidate and ln == start:
                note = f"Ứng viên đổi tên gần nhất trong AST: `{ast_node.qualname}`"
            context_lines.append(
                EvidenceLine(
                    line_number=ln,
                    content=code_lines[ln - 1] if ln - 1 < len(code_lines) else "",
                    is_target=is_target,
                    annotation=note,
                )
            )

        target_sorted = sorted(pinpoint_lines.keys()) if pinpoint_lines else [start]
        exact_quote = "\n".join(
            code_lines[ln - 1] for ln in target_sorted if 0 <= ln - 1 < len(code_lines)
        )

        return EvidenceSourceBlock(
            source_type="ast_code",
            file_path=ast_node.file_path,
            start_line=target_sorted[0],
            end_line=target_sorted[-1],
            exact_quote=exact_quote,
            context_lines=context_lines,
            ast_node_proof=node_proof,
        )

    def _extract_python_node_evidences(
        self, file_path: str, source: str, lines: List[str]
    ) -> List[_AstNodeEvidence]:
        results: List[_AstNodeEvidence] = []
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return results

        mutating_verbs = self._MUTATING_VERBS

        class Visitor(ast.NodeVisitor):
            def __init__(self) -> None:
                self.current_class: Optional[str] = None

            def visit_ClassDef(self, node: ast.ClassDef) -> None:
                prev = self.current_class
                self.current_class = node.name
                self.generic_visit(node)
                self.current_class = prev

            def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
                self._handle_func(node)

            def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
                self._handle_func(node)

            def _handle_func(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
                end_line = getattr(node, "end_lineno", node.lineno)
                first_body_line = node.body[0].lineno if node.body else node.lineno
                sig_end = max(node.lineno, first_body_line - 1)
                sig_text = " ".join(
                    line.strip() for line in lines[node.lineno - 1 : sig_end]
                ).rstrip(":")

                ret_type = ast.unparse(node.returns) if node.returns else None
                raise_lines: List[Tuple[int, str, str]] = []
                mutating_lines: List[Tuple[int, str, str]] = []
                return_lines: List[Tuple[int, str]] = []

                for child in ast.walk(node):
                    if isinstance(child, ast.Raise) and child.exc is not None:
                        exc_name = ast.unparse(child.exc.func) if isinstance(child.exc, ast.Call) else ast.unparse(child.exc)
                        stmt = lines[child.lineno - 1].strip() if 0 <= child.lineno - 1 < len(lines) else ast.unparse(child)
                        raise_lines.append((child.lineno, exc_name, stmt))
                    elif isinstance(child, ast.Call):
                        fn_name = ast.unparse(child.func)
                        if any(v in fn_name.lower() for v in mutating_verbs):
                            stmt = lines[child.lineno - 1].strip() if 0 <= child.lineno - 1 < len(lines) else ast.unparse(child)
                            mutating_lines.append((child.lineno, fn_name, stmt))
                    elif isinstance(child, ast.Return) and child.value is not None:
                        if not (isinstance(child.value, ast.Constant) and child.value.value is None):
                            stmt = lines[child.lineno - 1].strip() if 0 <= child.lineno - 1 < len(lines) else ast.unparse(child)
                            return_lines.append((child.lineno, stmt))

                qualname = f"{self.current_class}.{node.name}" if self.current_class else node.name
                results.append(
                    _AstNodeEvidence(
                        name=node.name,
                        qualname=qualname,
                        kind="method" if self.current_class else "function",
                        file_path=file_path,
                        start_line=node.lineno,
                        end_line=end_line,
                        signature_end_line=sig_end,
                        signature_text=sig_text,
                        return_type=ret_type,
                        raise_lines=sorted(set(raise_lines), key=lambda x: x[0]),
                        mutating_call_lines=sorted(set(mutating_lines), key=lambda x: x[0]),
                        return_lines=sorted(set(return_lines), key=lambda x: x[0]),
                    )
                )

        Visitor().visit(tree)
        return results

    def _build_ai_grounding_payload(
        self,
        drift: DriftItem,
        grounding_status: str,
        doc_evidence: EvidenceSourceBlock,
        code_evidence: Optional[EvidenceSourceBlock],
        ast_facts: List[str],
        related_symbols: List[str],
    ) -> str:
        lines: List[str] = [
            f"[GROUNDING_EVIDENCE | ID={drift.drift_id} | SEVERITY={drift.severity.value.upper()} ({drift.severity_score}/100) | STATUS={grounding_status}]",
            f"1. DRIFT_SUMMARY: [{drift.category.value.upper()}/{drift.sub_type}] {drift.title}",
            f"2. DOC_ANCHOR ({doc_evidence.file_path} L{doc_evidence.start_line}-L{doc_evidence.end_line}):",
            f"   {doc_evidence.exact_quote}",
        ]
        if code_evidence:
            lines.append(
                f"3. AST_ANCHOR ({code_evidence.file_path} L{code_evidence.start_line}-L{code_evidence.end_line}):"
            )
            lines.append(f"   {code_evidence.exact_quote}")
            if code_evidence.ast_node_proof:
                lines.append(f"   AST_NODE_PROOF: {code_evidence.ast_node_proof}")
        else:
            lines.append("3. AST_ANCHOR: MISSING_IN_CODE (Không tồn tại trong cây AST)")

        lines.append("4. VERIFIED_AST_FACTS:")
        for fact in ast_facts:
            lines.append(f"   - {fact}")

        lines.append(
            "5. REPAIR_CONSTRAINT: Chỉ cập nhật phần tài liệu tại DOC_ANCHOR dựa trên VERIFIED_AST_FACTS. "
            f"Các ký hiệu hợp lệ duy nhất trong module: {', '.join(related_symbols) if related_symbols else 'None'}. "
            "Tuyệt đối không tự bịa thêm tham số, kiểu trả về hoặc hàm ngoài danh sách này."
        )
        return "\n".join(lines)