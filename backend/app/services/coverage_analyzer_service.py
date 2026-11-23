from typing import List, Optional
from app.schemas.ast_doc import (
    ASTParseResponse,
    CodeEntity,
    CoverageReport,
    DocumentationGap,
    GapSeverity,
)
from app.services.ast_parser_service import ast_parser_service


class CoverageAnalyzerService:
    """Module 4.2: Documentation Coverage Gap Identification Analyzer."""

    SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}

    def analyze_from_code(
        self, file_path: str, source_code: str, language: Optional[str] = None
    ) -> CoverageReport:
        parse_result = ast_parser_service.parse_code(
            file_path=file_path, source_code=source_code, language=language
        )
        return self.analyze_ast(parse_result)

    def analyze_ast(self, parse_result: ASTParseResponse) -> CoverageReport:
        entities = parse_result.entities
        total = len(entities)

        if total == 0:
            return CoverageReport(
                file_path=parse_result.file_path,
                language=parse_result.language,
                total_entities=0,
                documented_entities=0,
                undocumented_entities=0,
                coverage_percentage=100.0,
                weighted_coverage_percentage=100.0,
                status="good",
                high_priority_gaps=0,
                gaps=[],
            )

        documented = sum(1 for e in entities if e.has_docstring)
        undocumented = total - documented
        coverage_pct = round((documented / total) * 100, 2)

        total_weight = sum(max(1, e.complexity_score) for e in entities)
        documented_weight = sum(
            max(1, e.complexity_score) for e in entities if e.has_docstring
        )
        weighted_pct = round((documented_weight / total_weight) * 100, 2)

        gaps: List[DocumentationGap] = []
        for entity in entities:
            gaps.extend(self._evaluate_entity(entity))

        gaps.sort(
            key=lambda g: (self.SEVERITY_ORDER[g.severity], -g.complexity_score, g.start_line)
        )

        high_count = sum(1 for g in gaps if g.severity == "high")
        if coverage_pct >= 80.0 and high_count == 0:
            status = "good"
        elif coverage_pct >= 40.0:
            status = "needs_improvement"
        else:
            status = "critical"

        return CoverageReport(
            file_path=parse_result.file_path,
            language=parse_result.language,
            total_entities=total,
            documented_entities=documented,
            undocumented_entities=undocumented,
            coverage_percentage=coverage_pct,
            weighted_coverage_percentage=weighted_pct,
            status=status,
            high_priority_gaps=high_count,
            gaps=gaps,
        )

    def _is_internal_or_dunder(self, name: str) -> bool:
        return name.startswith("_")

    def _determine_missing_doc_severity(self, entity: CodeEntity) -> GapSeverity:
        if self._is_internal_or_dunder(entity.name):
            return "high" if entity.complexity_score >= 8 else "low"
        if entity.entity_type == "class" or entity.complexity_score >= 4:
            return "high"
        return "medium"

    def _evaluate_entity(self, entity: CodeEntity) -> List[DocumentationGap]:
        entity_gaps: List[DocumentationGap] = []
        display_name = (
            f"{entity.parent_name}.{entity.name}" if entity.parent_name else entity.name
        )

        # 1. Kiểm tra thiếu Docstring / JSDoc
        if not entity.has_docstring:
            severity = self._determine_missing_doc_severity(entity)
            param_names = ", ".join(p.name for p in entity.parameters)
            param_hint = f" và các tham số ({param_names})" if param_names else ""
            entity_gaps.append(
                DocumentationGap(
                    entity_name=entity.name,
                    entity_type=entity.entity_type,
                    parent_name=entity.parent_name,
                    signature=entity.signature,
                    start_line=entity.start_line,
                    end_line=entity.end_line,
                    complexity_score=entity.complexity_score,
                    gap_type="missing_docstring",
                    severity=severity,
                    recommendation=(
                        f"Bổ sung tài liệu mô tả mục đích của `{display_name}`"
                        f"{param_hint} (độ phức tạp: {entity.complexity_score})."
                    ),
                )
            )
        # 2. Kiểm tra Docstring quá sơ sài trên hàm phức tạp
        elif entity.docstring and len(entity.docstring.strip()) < 20 and entity.complexity_score >= 5:
            entity_gaps.append(
                DocumentationGap(
                    entity_name=entity.name,
                    entity_type=entity.entity_type,
                    parent_name=entity.parent_name,
                    signature=entity.signature,
                    start_line=entity.start_line,
                    end_line=entity.end_line,
                    complexity_score=entity.complexity_score,
                    gap_type="brief_docstring",
                    severity="low",
                    recommendation=(
                        f"Docstring của `{display_name}` quá ngắn so với độ phức tạp ({entity.complexity_score}); "
                        "nên bổ sung chi tiết luồng xử lý và giá trị trả về."
                    ),
                )
            )

        # 3. Kiểm tra thiếu Type Annotation trên hàm/method public
        if entity.entity_type in ("function", "method") and not self._is_internal_or_dunder(
            entity.name
        ):
            untyped_params = [p.name for p in entity.parameters if not p.type_annotation]
            if untyped_params or entity.return_type is None:
                missing_parts = []
                if untyped_params:
                    missing_parts.append(f"tham số `{', '.join(untyped_params)}`")
                if entity.return_type is None:
                    missing_parts.append("kiểu trả về")
                entity_gaps.append(
                    DocumentationGap(
                        entity_name=entity.name,
                        entity_type=entity.entity_type,
                        parent_name=entity.parent_name,
                        signature=entity.signature,
                        start_line=entity.start_line,
                        end_line=entity.end_line,
                        complexity_score=entity.complexity_score,
                        gap_type="missing_type_hints",
                        severity="low",
                        recommendation=(
                            f"Bổ sung type annotation cho {' và '.join(missing_parts)} "
                            f"tại `{display_name}` để AI sinh tài liệu chính xác hơn."
                        ),
                    )
                )

        return entity_gaps


coverage_analyzer_service = CoverageAnalyzerService()