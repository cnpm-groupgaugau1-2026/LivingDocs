import ast
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from app.schemas.multimodal import (
    ArchitecturalClaimSchema,
    ClaimVerificationResultSchema,
    CodeEvidenceSchema,
    GraphNodeSchema,
    VisionContextExtractionResponse,
    VisualCodeConsistencyResponse,
)
from app.services.vision_context_extractor_service import VisionContextExtractor


class VisualAssetConsistencyVerifier:
    """
    FE05.3 - Visual Asset - Code Consistency Verification Pipeline
    Kết nối đầu ra đồ thị & khẳng định kiến trúc từ FE05.2 (VisionContextExtractor)
    với bộ lập chỉ mục mã nguồn thật (Python AST + API Route Scanner) để phát hiện Drift.
    """

    IGNORED_DIRS: Set[str] = {
        ".git",
        ".next",
        "__pycache__",
        "node_modules",
        "venv",
        ".venv",
        "env",
        "dist",
        "build",
        ".pytest_cache",
    }

    def __init__(self) -> None:
        self.vision_extractor = VisionContextExtractor()

    async def verify_consistency(
        self,
        file_bytes: bytes,
        filename: str,
        content_type: str = "",
        context_hint: str = "",
        repo_path: str = "",
    ) -> VisualCodeConsistencyResponse:
        # 1. Chạy pipeline FE05.1 (OCR) + FE05.2 (Vision-LLM Graph & Claims)
        vision_context: VisionContextExtractionResponse = (
            await self.vision_extractor.extract_context(
                file_bytes=file_bytes,
                filename=filename,
                content_type=content_type,
                context_hint=context_hint,
            )
        )

        # 2. Xác định thư mục gốc mã nguồn cần quét (mặc định là thư mục dự án LivingDocs)
        target_root = self._resolve_repo_root(repo_path)
        code_index = self._index_repository(target_root)

        # 3. Đối chiếu từng Architectural Claim & Node với chỉ mục mã nguồn thật
        node_lookup: Dict[str, GraphNodeSchema] = {
            node.label: node for node in vision_context.nodes
        }
        results: List[ClaimVerificationResultSchema] = []

        for claim in vision_context.architectural_claims:
            res = self._verify_single_claim(
                claim=claim,
                node_lookup=node_lookup,
                code_index=code_index,
            )
            results.append(res)

        # 4. Tính toán điểm nhất quán tổng thể (Consistency Score)
        total = len(results)
        consistent_cnt = sum(1 for r in results if r.status == "consistent")
        drifted_cnt = sum(1 for r in results if r.status == "drifted")
        unverified_cnt = sum(1 for r in results if r.status == "unverified")

        if total == 0:
            score = 1.0
        else:
            # Nhất quán = 1.0 điểm, Chưa triển khai (unverified) = 0.35 điểm, Sai lệch (drifted) = 0.0 điểm
            weighted = (consistent_cnt * 1.0) + (unverified_cnt * 0.35)
            score = round(weighted / total, 4)

        if drifted_cnt == 0 and unverified_cnt == 0:
            overall_status = "consistent"
        elif score >= 0.65:
            overall_status = "partial_drift"
        else:
            overall_status = "major_drift"

        return VisualCodeConsistencyResponse(
            filename=filename,
            asset_type=vision_context.asset_type,
            scanned_repo_root=str(target_root),
            scanned_files_count=code_index["files_count"],
            indexed_symbols_count=code_index["symbols_count"],
            consistency_score=score,
            overall_status=overall_status,
            total_claims=total,
            consistent_count=consistent_cnt,
            drifted_count=drifted_cnt,
            unverified_count=unverified_cnt,
            semantic_summary=vision_context.semantic_summary,
            verification_results=results,
            vision_context=vision_context,
        )

    def _resolve_repo_root(self, repo_path: str) -> Path:
        if repo_path and repo_path.strip():
            candidate = Path(repo_path.strip()).expanduser().resolve()
            if candidate.exists() and candidate.is_dir():
                return candidate

        # Tự động lùi từ backend/app/services/visual_consistency_service.py về thư mục gốc dự án LivingDocs
        here = Path(__file__).resolve()
        backend_dir = here.parents[2]
        project_root = backend_dir.parent
        if (project_root / "backend").exists():
            return project_root
        return backend_dir

    def _index_repository(self, root: Path) -> Dict[str, Any]:
        """
        Quét toàn bộ tệp Python (.py) và TypeScript/JavaScript (.ts, .tsx, .js)
        để trích xuất Class, Function, API Route và lời gọi hàm nội bộ.
        """
        classes: Dict[str, List[CodeEvidenceSchema]] = {}
        functions: Dict[str, List[CodeEvidenceSchema]] = {}
        endpoints: List[Tuple[str, CodeEvidenceSchema]] = []
        calls_by_file: Dict[str, Set[str]] = {}
        file_paths: List[str] = []

        files_scanned = 0
        symbols_total = 0

        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in self.IGNORED_DIRS]

            for fname in filenames:
                ext = Path(fname).suffix.lower()
                if ext not in {".py", ".ts", ".tsx", ".js"}:
                    continue

                full_path = Path(dirpath) / fname
                try:
                    rel_path = full_path.relative_to(root).as_posix()
                except ValueError:
                    rel_path = full_path.as_posix()

                file_paths.append(rel_path)
                files_scanned += 1

                try:
                    source_text = full_path.read_text(encoding="utf-8", errors="ignore")
                except Exception:
                    continue

                lines = source_text.splitlines()

                if ext == ".py":
                    c_cnt, f_cnt, e_cnt = self._parse_python_ast(
                        source_text=source_text,
                        lines=lines,
                        rel_path=rel_path,
                        classes=classes,
                        functions=functions,
                        endpoints=endpoints,
                        calls_by_file=calls_by_file,
                    )
                    symbols_total += c_cnt + f_cnt + e_cnt
                else:
                    s_cnt = self._parse_ts_symbols(
                        lines=lines,
                        rel_path=rel_path,
                        classes=classes,
                        functions=functions,
                    )
                    symbols_total += s_cnt

        return {
            "files_count": files_scanned,
            "symbols_count": symbols_total,
            "file_paths": file_paths,
            "classes": classes,
            "functions": functions,
            "endpoints": endpoints,
            "calls_by_file": calls_by_file,
        }

    def _parse_python_ast(
        self,
        source_text: str,
        lines: List[str],
        rel_path: str,
        classes: Dict[str, List[CodeEvidenceSchema]],
        functions: Dict[str, List[CodeEvidenceSchema]],
        endpoints: List[Tuple[str, CodeEvidenceSchema]],
        calls_by_file: Dict[str, Set[str]],
    ) -> Tuple[int, int, int]:
        c_cnt = f_cnt = e_cnt = 0
        try:
            tree = ast.parse(source_text, filename=rel_path)
        except SyntaxError:
            return (0, 0, 0)

        # Tìm router prefix nếu có (vd: APIRouter(prefix="/api/v1/multimodal"))
        router_prefix = ""
        prefix_match = re.search(r'APIRouter\([^)]*prefix\s*=\s*["\']([^"\']+)["\']', source_text)
        if prefix_match:
            router_prefix = prefix_match.group(1).rstrip("/")

        file_calls: Set[str] = set()

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                snippet = lines[node.lineno - 1].strip() if node.lineno <= len(lines) else ""
                ev = CodeEvidenceSchema(
                    file_path=rel_path,
                    line_number=node.lineno,
                    symbol_name=node.name,
                    symbol_type="class",
                    snippet=snippet,
                )
                classes.setdefault(node.name, []).append(ev)
                c_cnt += 1

            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                snippet = lines[node.lineno - 1].strip() if node.lineno <= len(lines) else ""
                ev = CodeEvidenceSchema(
                    file_path=rel_path,
                    line_number=node.lineno,
                    symbol_name=node.name,
                    symbol_type="function",
                    snippet=snippet,
                )
                functions.setdefault(node.name, []).append(ev)
                f_cnt += 1

                # Kiểm tra decorator FastAPI route (@router.post("/ocr"), @app.get(...))
                for dec in node.decorator_list:
                    route_info = self._extract_fastapi_route(dec, router_prefix)
                    if route_info:
                        dec_line = getattr(dec, "lineno", node.lineno)
                        dec_snip = lines[dec_line - 1].strip() if dec_line <= len(lines) else snippet
                        ep_ev = CodeEvidenceSchema(
                            file_path=rel_path,
                            line_number=dec_line,
                            symbol_name=route_info,
                            symbol_type="endpoint",
                            snippet=dec_snip,
                        )
                        endpoints.append((route_info, ep_ev))
                        e_cnt += 1

            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    file_calls.add(node.func.id)
                elif isinstance(node.func, ast.Attribute):
                    file_calls.add(node.func.attr)

        calls_by_file[rel_path] = file_calls
        return (c_cnt, f_cnt, e_cnt)

    def _extract_fastapi_route(self, dec: ast.AST, router_prefix: str) -> Optional[str]:
        if not isinstance(dec, ast.Call) or not isinstance(dec.func, ast.Attribute):
            return None
        method = dec.func.attr.upper()
        if method not in {"GET", "POST", "PUT", "DELETE", "PATCH"}:
            return None
        if not dec.args:
            return None
        first_arg = dec.args[0]
        if isinstance(first_arg, ast.Constant) and isinstance(first_arg.value, str):
            sub_path = first_arg.value
            full_path = f"{router_prefix}/{sub_path.lstrip('/')}".rstrip("/")
            if not full_path.startswith("/"):
                full_path = f"/{full_path}"
            return f"{method} {full_path}"
        return None

    def _parse_ts_symbols(
        self,
        lines: List[str],
        rel_path: str,
        classes: Dict[str, List[CodeEvidenceSchema]],
        functions: Dict[str, List[CodeEvidenceSchema]],
    ) -> int:
        count = 0
        for idx, line in enumerate(lines, start=1):
            stripped = line.strip()
            m_fn = re.match(r"^(?:export\s+)?(?:async\s+)?function\s+([A-Za-z0-9_]+)\s*\(", stripped)
            if m_fn:
                name = m_fn.group(1)
                ev = CodeEvidenceSchema(
                    file_path=rel_path,
                    line_number=idx,
                    symbol_name=name,
                    symbol_type="function",
                    snippet=stripped[:120],
                )
                if name[0].isupper():
                    classes.setdefault(name, []).append(ev)
                else:
                    functions.setdefault(name, []).append(ev)
                count += 1
        return count

    def _verify_single_claim(
        self,
        claim: ArchitecturalClaimSchema,
        node_lookup: Dict[str, GraphNodeSchema],
        code_index: Dict[str, Any],
    ) -> ClaimVerificationResultSchema:
        cat = claim.category.lower()

        if cat == "api_contract":
            return self._verify_api_contract(claim, code_index)
        if cat == "code_mapping":
            return self._verify_code_mapping(claim, node_lookup, code_index)
        return self._verify_dependency_or_persistence(claim, node_lookup, code_index)

    def _verify_api_contract(
        self,
        claim: ArchitecturalClaimSchema,
        code_index: Dict[str, Any],
    ) -> ClaimVerificationResultSchema:
        target_ep = claim.verifiable_target.strip()
        indexed_eps: List[Tuple[str, CodeEvidenceSchema]] = code_index["endpoints"]

        # 1. Khớp chính xác METHOD + PATH
        exact_matches = [ev for ep_str, ev in indexed_eps if ep_str.lower() == target_ep.lower()]
        if exact_matches:
            return ClaimVerificationResultSchema(
                claim_id=claim.claim_id,
                category=claim.category,
                statement=claim.statement,
                verifiable_target=target_ep,
                status="consistent",
                severity="info",
                confidence=0.96,
                explanation=f"Đã xác minh endpoint '{target_ep}' được khai báo khớp hoàn toàn trong router backend.",
                remediation="Không cần hành động — tài liệu và mã nguồn đồng nhất.",
                evidences=exact_matches[:3],
            )

        # 2. Khớp gần đúng theo đuôi path hoặc từ khóa nghiệp vụ -> phát hiện API Contract Drift
        target_parts = target_ep.split()
        target_path = target_parts[-1].lower() if target_parts else target_ep.lower()
        target_leaf = target_path.rstrip("/").split("/")[-1]

        partial_matches = [
            ev
            for ep_str, ev in indexed_eps
            if target_leaf and len(target_leaf) >= 3 and target_leaf in ep_str.lower()
        ]
        if partial_matches:
            actual = partial_matches[0].symbol_name
            return ClaimVerificationResultSchema(
                claim_id=claim.claim_id,
                category=claim.category,
                statement=claim.statement,
                verifiable_target=target_ep,
                status="drifted",
                severity="critical",
                confidence=0.91,
                explanation=(
                    f"Phát hiện sai lệch hợp đồng API (API Drift): Sơ đồ mô tả '{target_ep}' "
                    f"nhưng mã nguồn hiện tại đang triển khai '{actual}'."
                ),
                remediation=f"Cập nhật lại đường dẫn trên sơ đồ thành '{actual}' hoặc điều chỉnh route trong {partial_matches[0].file_path}.",
                evidences=partial_matches[:3],
            )

        return ClaimVerificationResultSchema(
            claim_id=claim.claim_id,
            category=claim.category,
            statement=claim.statement,
            verifiable_target=target_ep,
            status="unverified",
            severity="warning",
            confidence=0.85,
            explanation=f"Chưa tìm thấy route '{target_ep}' trong {code_index['files_count']} tệp mã nguồn được quét.",
            remediation=f"Bổ sung endpoint '{target_ep}' vào tầng API router hoặc kiểm tra phạm vi thư mục quét.",
            evidences=[],
        )

    def _verify_code_mapping(
        self,
        claim: ArchitecturalClaimSchema,
        node_lookup: Dict[str, GraphNodeSchema],
        code_index: Dict[str, Any],
    ) -> ClaimVerificationResultSchema:
        entities = claim.involved_entities or []
        node_name = entities[0] if len(entities) >= 1 else ""
        raw_func = entities[1] if len(entities) >= 2 else ""
        clean_func = raw_func.rstrip("()").strip()
        target_file = claim.verifiable_target.strip()

        classes_idx: Dict[str, List[CodeEvidenceSchema]] = code_index["classes"]
        funcs_idx: Dict[str, List[CodeEvidenceSchema]] = code_index["functions"]
        all_files: List[str] = code_index["file_paths"]

        matched_evidences: List[CodeEvidenceSchema] = []
        if clean_func and clean_func in funcs_idx:
            matched_evidences.extend(funcs_idx[clean_func])
        if node_name and node_name in classes_idx:
            matched_evidences.extend(classes_idx[node_name])

        # Kiểm tra nếu có đường dẫn tệp cụ thể gắn với claim
        has_explicit_path = "/" in target_file or target_file.endswith(".py")
        file_exists = any(
            target_file.replace("\\", "/") in fp for fp in all_files
        ) if has_explicit_path else False

        if matched_evidences:
            # Nếu sơ đồ chỉ định tệp A nhưng hàm lại nằm ở tệp B -> báo drifted
            if has_explicit_path and not file_exists:
                actual_file = matched_evidences[0].file_path
                return ClaimVerificationResultSchema(
                    claim_id=claim.claim_id,
                    category=claim.category,
                    statement=claim.statement,
                    verifiable_target=target_file,
                    status="drifted",
                    severity="warning",
                    confidence=0.90,
                    explanation=(
                        f"Hàm '{raw_func}' tồn tại trong mã nguồn tại '{actual_file}' (dòng {matched_evidences[0].line_number}) "
                        f"nhưng không nằm ở đường dẫn '{target_file}' như sơ đồ mô tả."
                    ),
                    remediation=f"Cập nhật tham chiếu tệp trên sơ đồ từ '{target_file}' sang '{actual_file}'.",
                    evidences=matched_evidences[:3],
                )

            return ClaimVerificationResultSchema(
                claim_id=claim.claim_id,
                category=claim.category,
                statement=claim.statement,
                verifiable_target=target_file,
                status="consistent",
                severity="info",
                confidence=0.95,
                explanation=(
                    f"Đã đối chiếu thành công '{raw_func or node_name}' tại "
                    f"{matched_evidences[0].file_path}:{matched_evidences[0].line_number}."
                ),
                remediation="Không cần hành động — ánh xạ hàm và thành phần khớp với mã nguồn.",
                evidences=matched_evidences[:3],
            )

        # Kiểm tra khớp gần đúng tên hàm theo từ khóa (phát hiện đổi tên hàm - Symbol Rename Drift)
        if clean_func:
            tokens = [t for t in clean_func.split("_") if len(t) >= 4]
            similar_evs: List[CodeEvidenceSchema] = []
            for fn_name, ev_list in funcs_idx.items():
                if any(tok in fn_name for tok in tokens):
                    similar_evs.extend(ev_list)
            if similar_evs:
                return ClaimVerificationResultSchema(
                    claim_id=claim.claim_id,
                    category=claim.category,
                    statement=claim.statement,
                    verifiable_target=target_file,
                    status="drifted",
                    severity="warning",
                    confidence=0.86,
                    explanation=(
                        f"Không tìm thấy hàm '{raw_func}', nhưng phát hiện hàm tương đồng "
                        f"'{similar_evs[0].symbol_name}()' tại {similar_evs[0].file_path}:{similar_evs[0].line_number}."
                    ),
                    remediation=f"Đồng bộ tên hàm trên sơ đồ thành '{similar_evs[0].symbol_name}()' nếu hàm đã được tái cấu trúc.",
                    evidences=similar_evs[:2],
                )

        return ClaimVerificationResultSchema(
            claim_id=claim.claim_id,
            category=claim.category,
            statement=claim.statement,
            verifiable_target=target_file,
            status="unverified",
            severity="warning",
            confidence=0.84,
            explanation=f"Thành phần '{node_name}' hoặc hàm '{raw_func}' chưa được triển khai trong mã nguồn được quét.",
            remediation=f"Triển khai hàm '{raw_func}' cho '{node_name}' hoặc loại bỏ thành phần lỗi thời khỏi tài liệu.",
            evidences=[],
        )

    def _verify_dependency_or_persistence(
        self,
        claim: ArchitecturalClaimSchema,
        node_lookup: Dict[str, GraphNodeSchema],
        code_index: Dict[str, Any],
    ) -> ClaimVerificationResultSchema:
        entities = claim.involved_entities or []
        src_name = entities[0] if len(entities) >= 1 else ""
        dst_name = entities[1] if len(entities) >= 2 else claim.verifiable_target

        classes_idx: Dict[str, List[CodeEvidenceSchema]] = code_index["classes"]
        funcs_idx: Dict[str, List[CodeEvidenceSchema]] = code_index["functions"]
        calls_by_file: Dict[str, Set[str]] = code_index["calls_by_file"]

        src_evs = classes_idx.get(src_name, [])
        dst_evs = classes_idx.get(dst_name, [])

        # Kiểm tra xem tệp chứa src_name có gọi tới dst_name hoặc các hàm của dst_name không
        dst_node = node_lookup.get(dst_name)
        dst_funcs = {f.rstrip("()") for f in (dst_node.functions if dst_node else [])}

        call_verified = False
        evidences: List[CodeEvidenceSchema] = []

        if src_evs:
            evidences.extend(src_evs[:1])
            for s_ev in src_evs:
                called_symbols = calls_by_file.get(s_ev.file_path, set())
                if dst_name in called_symbols or bool(dst_funcs & called_symbols):
                    call_verified = True
                    break

        if dst_evs:
            evidences.extend(dst_evs[:1])
        else:
            for fn in dst_funcs:
                if fn in funcs_idx:
                    evidences.extend(funcs_idx[fn][:1])

        if src_evs and dst_evs and call_verified:
            return ClaimVerificationResultSchema(
                claim_id=claim.claim_id,
                category=claim.category,
                statement=claim.statement,
                verifiable_target=dst_name,
                status="consistent",
                severity="info",
                confidence=0.94,
                explanation=f"Đã xác minh cả '{src_name}' và '{dst_name}' cùng lời gọi phụ thuộc trực tiếp trong mã nguồn.",
                remediation="Không cần hành động — luồng tương tác kiến trúc khớp với mã nguồn.",
                evidences=evidences,
            )

        if src_evs and not dst_evs and not evidences[1:]:
            return ClaimVerificationResultSchema(
                claim_id=claim.claim_id,
                category=claim.category,
                statement=claim.statement,
                verifiable_target=dst_name,
                status="drifted",
                severity="critical",
                confidence=0.88,
                explanation=(
                    f"Phát hiện sai lệch phụ thuộc (Dependency Drift): '{src_name}' tồn tại trong mã nguồn "
                    f"nhưng dịch vụ đích '{dst_name}' không tồn tại."
                ),
                remediation=f"Kiểm tra lại kết nối từ '{src_name}' tới '{dst_name}' và cập nhật sơ đồ kiến trúc.",
                evidences=evidences,
            )

        if src_evs and dst_evs and not call_verified:
            return ClaimVerificationResultSchema(
                claim_id=claim.claim_id,
                category=claim.category,
                statement=claim.statement,
                verifiable_target=dst_name,
                status="drifted",
                severity="warning",
                confidence=0.85,
                explanation=(
                    f"Cả '{src_name}' và '{dst_name}' đều tồn tại, nhưng chưa phát hiện lời gọi trực tiếp "
                    f"từ '{src_name}' sang '{dst_name}' trong AST."
                ),
                remediation=f"Bổ sung lời gọi tích hợp từ '{src_name}' sang '{dst_name}' hoặc gỡ mũi tên trên sơ đồ.",
                evidences=evidences,
            )

        return ClaimVerificationResultSchema(
            claim_id=claim.claim_id,
            category=claim.category,
            statement=claim.statement,
            verifiable_target=dst_name,
            status="unverified",
            severity="warning",
            confidence=0.82,
            explanation=f"Chưa tìm thấy cặp thành phần '{src_name}' -> '{dst_name}' trong mã nguồn được quét.",
            remediation="Triển khai các module tương ứng hoặc chỉ định đúng đường dẫn repository cần đối chiếu.",
            evidences=evidences,
        )