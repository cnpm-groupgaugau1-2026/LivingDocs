from typing import List, Optional, Literal
from pydantic import BaseModel, Field


class CodeParameter(BaseModel):
    name: str
    type_annotation: Optional[str] = None
    default_value: Optional[str] = None


class CodeEntity(BaseModel):
    entity_type: Literal["class", "function", "method"]
    name: str
    parent_name: Optional[str] = None
    signature: str
    start_line: int
    end_line: int
    parameters: List[CodeParameter] = Field(default_factory=list)
    return_type: Optional[str] = None
    docstring: Optional[str] = None
    has_docstring: bool = False
    complexity_score: int = 1  # Đếm số nhánh rẽ (if/for/while/try) để đánh giá độ phức tạp


class ASTParseRequest(BaseModel):
    file_path: str = Field(..., example="app/services/auth_service.py")
    language: Optional[str] = Field(None, example="python")
    source_code: str


class ASTParseResponse(BaseModel):
    file_path: str
    language: str
    total_entities: int
    documented_entities: int
    entities: List[CodeEntity]

GapSeverity = Literal["high", "medium", "low"]
GapType = Literal["missing_docstring", "brief_docstring", "missing_type_hints"]


class DocumentationGap(BaseModel):
    entity_name: str
    entity_type: Literal["class", "function", "method"]
    parent_name: Optional[str] = None
    signature: str
    start_line: int
    end_line: int
    complexity_score: int
    gap_type: GapType
    severity: GapSeverity
    recommendation: str


class CoverageReport(BaseModel):
    file_path: str
    language: str
    total_entities: int
    documented_entities: int
    undocumented_entities: int
    coverage_percentage: float
    weighted_coverage_percentage: float
    status: Literal["good", "needs_improvement", "critical"]
    high_priority_gaps: int
    gaps: List[DocumentationGap] = Field(default_factory=list)

class DraftGenerationRequest(BaseModel):
    file_path: str = Field(..., example="app/services/ast_parser_service.py")
    source_code: str
    language: Optional[str] = Field(None, example="python")
    template_id: Optional[int] = Field(None, description="ID mẫu tài liệu trong bảng doc_templates (FE11)")
    template_slug: Optional[str] = Field(None, description="Slug mẫu tài liệu nếu không truyền template_id")
    custom_instructions: Optional[str] = Field(
        None, example="Tập trung giải thích rõ luồng xử lý tham số và ngoại lệ."
    )
    include_coverage_gaps: bool = Field(
        True, description="Đính kèm phân tích lỗ hổng tài liệu (Module 4.2) vào ngữ cảnh sinh tài liệu"
    )


class DraftGenerationResponse(BaseModel):
    file_path: str
    language: str
    template_used: str
    generation_mode: Literal["llm_live", "ast_template_fallback"]
    provider_used: str
    model_used: str
    tokens_estimated: int
    markdown_content: str
    ast_summary: ASTParseResponse
    coverage_report: CoverageReport
    warnings: List[str] = Field(default_factory=list)