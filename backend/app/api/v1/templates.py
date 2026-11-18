import json
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.rbac import RequireRole, get_current_user
from app.models.template import DocTemplate, DocTemplateVersion
from app.models.user import Role, User

router = APIRouter(prefix="/api/v1/templates", tags=["FE11 Dynamic Template Library"])

# ==============================================================================
# --- DANH MỤC AST CODE-ENTITY PLACEHOLDERS CHUẨN (3.1) ---
# ==============================================================================

STANDARD_AST_PLACEHOLDERS = [
    {
        "placeholder": "{{project.name}}",
        "ast_source": "ast.repository.name",
        "data_type": "inline_text",
        "description": "Tên Repository / Dự án từ GitHub Workspace",
        "sample_value": "LivingDocs Enterprise",
    },
    {
        "placeholder": "{{module.name}}",
        "ast_source": "ast.module.identifier",
        "data_type": "inline_text",
        "description": "Tên package hoặc module đang được phân tích AST",
        "sample_value": "app.api.v1.templates",
    },
    {
        "placeholder": "{{api.endpoints}}",
        "ast_source": "ast.routers[*].endpoints",
        "data_type": "markdown_table",
        "description": "Bảng danh sách HTTP Method, Endpoint Path, Auth Guard và Response Schema",
        "sample_value": (
            "| Method | Endpoint | Auth Role | Description |\n"
            "| :--- | :--- | :--- | :--- |\n"
            "| `GET` | `/api/v1/templates` | `Authenticated` | Lấy danh sách template từ PostgreSQL |\n"
            "| `POST` | `/api/v1/templates` | `Tech Lead / Admin` | Tạo template & ánh xạ AST placeholder |\n"
            "| `POST` | `/api/v1/templates/{id}/validate-output` | `Tech Lead / Admin` | Kiểm định ràng buộc AI Output |"
        ),
    },
    {
        "placeholder": "{{classes.signatures}}",
        "ast_source": "ast.classes[*].signature",
        "data_type": "code_block",
        "description": "Chữ ký các Class, kế thừa và Docstring trích xuất từ AST",
        "sample_value": (
            "```python\n"
            "class DocTemplate(Base):\n"
            "    __tablename__ = 'doc_templates'\n"
            "    id: int\n"
            "    category: str  # API Reference | README | Module Guide | Onboarding Guide | ADR\n"
            "    is_enforced: bool\n"
            "```"
        ),
    },
    {
        "placeholder": "{{functions.list}}",
        "ast_source": "ast.functions[*].signature",
        "data_type": "bullet_list",
        "description": "Danh sách hàm, tham số đầu vào và kiểu dữ liệu trả về",
        "sample_value": (
            "- `render_template_with_ast(template_id: int, ast_context: dict) -> str`: Ánh xạ entity vào placeholder.\n"
            "- `enforce_formatting_constraints(markdown: str, rules: dict) -> ComplianceReport`: Kiểm tra cấu trúc đầu ra AI."
        ),
    },
    {
        "placeholder": "{{dependencies.graph}}",
        "ast_source": "ast.imports.dependencies",
        "data_type": "bullet_list",
        "description": "Các thư viện ngoài và module nội bộ được import",
        "sample_value": (
            "- **External:** `fastapi`, `sqlalchemy`, `pydantic`\n"
            "- **Internal:** `app.core.database`, `app.core.rbac`, `app.models.template`"
        ),
    },
    {
        "placeholder": "{{adr.context}}",
        "ast_source": "git.pull_request.context",
        "data_type": "paragraph",
        "description": "Bối cảnh kỹ thuật và vấn đề cần giải quyết từ Pull Request",
        "sample_value": "Hệ thống cần chuẩn hóa định dạng tài liệu kỹ thuật tự động sinh bởi LLM để tránh sai lệch cấu trúc giữa các microservice.",
    },
    {
        "placeholder": "{{adr.decision}}",
        "ast_source": "ast.diff.architectural_summary",
        "data_type": "paragraph",
        "description": "Quyết định kiến trúc được rút trích từ thay đổi mã nguồn",
        "sample_value": "Áp dụng Dynamic Template Management Library kết hợp AST Placeholder Mapping và AI Output Formatting Constraints Engine.",
    },
]


# ==============================================================================
# --- PYDANTIC SCHEMAS ---
# ==============================================================================

class PlaceholderMappingItem(BaseModel):
    placeholder: str = Field(..., min_length=3)
    ast_source: str = Field(..., min_length=2)
    data_type: str = Field(default="inline_text")
    fallback_value: str = Field(default="N/A")
    required: bool = Field(default=True)


class FormattingConstraintsSchema(BaseModel):
    required_sections: List[str] = Field(default_factory=list)
    forbidden_patterns: List[str] = Field(default_factory=lambda: ["TODO", "TBD", "FIXME"])
    tone_style: str = Field(default="Technical & Concise")
    require_code_blocks: bool = Field(default=True)
    require_tables_for_params: bool = Field(default=True)
    max_section_words: int = Field(default=400, ge=50, le=5000)
    enforce_strict_mode: bool = Field(default=True)


class TemplateCreateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=200)
    category: str = Field(..., min_length=2, max_length=80)
    description: str = Field(default="")
    content: str = Field(..., min_length=10)
    placeholder_mappings: List[PlaceholderMappingItem] = Field(default_factory=list)
    formatting_constraints: FormattingConstraintsSchema = Field(default_factory=FormattingConstraintsSchema)
    is_enforced: bool = Field(default=False)
    target_path_pattern: str = Field(default="docs/**/*.md")
    change_note: str = Field(default="Khởi tạo template mới")


class TemplateUpdateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=200)
    category: str = Field(..., min_length=2, max_length=80)
    description: str = Field(default="")
    content: str = Field(..., min_length=10)
    placeholder_mappings: List[PlaceholderMappingItem] = Field(default_factory=list)
    formatting_constraints: FormattingConstraintsSchema = Field(default_factory=FormattingConstraintsSchema)
    is_enforced: bool = Field(default=False)
    target_path_pattern: str = Field(default="docs/**/*.md")
    change_note: str = Field(default="Cập nhật cấu trúc template & ràng buộc AI")


class EnforceToggleRequest(BaseModel):
    is_enforced: bool
    target_path_pattern: Optional[str] = None


class PreviewTemplateRequest(BaseModel):
    content: Optional[str] = None
    placeholder_mappings: Optional[List[PlaceholderMappingItem]] = None
    custom_ast_overrides: Dict[str, str] = Field(default_factory=dict)


class ValidateAIOutputRequest(BaseModel):
    ai_generated_markdown: str = Field(..., min_length=1)


# ==============================================================================
# --- HELPER FUNCTIONS & DEFAULT TEMPLATE SEEDING ---
# ==============================================================================

def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", name.strip().lower()).strip("-")
    return slug or "template"


def _serialize_template(tpl: DocTemplate, version_count: int = 1) -> Dict[str, Any]:
    return {
        "id": tpl.id,
        "name": tpl.name,
        "slug": tpl.slug,
        "category": tpl.category,
        "description": tpl.description,
        "content": tpl.content,
        "placeholder_mappings": json.loads(tpl.placeholder_mappings_json or "[]"),
        "formatting_constraints": json.loads(tpl.formatting_constraints_json or "{}"),
        "current_version": tpl.current_version,
        "version_number": tpl.version_number,
        "version_count": version_count,
        "is_enforced": tpl.is_enforced,
        "target_path_pattern": tpl.target_path_pattern,
        "is_system_default": tpl.is_system_default,
        "created_by": tpl.created_by,
        "updated_by": tpl.updated_by,
        "created_at": tpl.created_at.isoformat() if tpl.created_at else None,
        "updated_at": tpl.updated_at.isoformat() if tpl.updated_at else None,
    }


def _seed_default_templates(db: Session) -> None:
    if db.query(DocTemplate).count() > 0:
        return

    defaults = [
        {
            "name": "Enterprise REST API Reference",
            "slug": "enterprise-rest-api-reference",
            "category": "API Reference",
            "description": "Chuẩn tài liệu đặc tả REST API tự động trích xuất Endpoint, Schema và mã lỗi từ FastAPI Router.",
            "is_enforced": True,
            "target_path_pattern": "docs/api/**/*.md",
            "content": (
                "# {{project.name}} — API Reference (`{{module.name}}`)\n\n"
                "## Overview\n"
                "Tài liệu đặc tả kỹ thuật cho module `{{module.name}}`, được đồng bộ tự động từ mã nguồn AST.\n\n"
                "## Authentication & RBAC\n"
                "Tất cả request yêu cầu header `Authorization: Bearer <JWT_TOKEN>` với quyền tương ứng.\n\n"
                "## Endpoints Specification\n"
                "{{api.endpoints}}\n\n"
                "## Data Models & Schemas\n"
                "{{classes.signatures}}\n\n"
                "## Dependencies\n"
                "{{dependencies.graph}}\n"
            ),
            "mappings": [
                {"placeholder": "{{project.name}}", "ast_source": "ast.repository.name", "data_type": "inline_text", "fallback_value": "LivingDocs", "required": True},
                {"placeholder": "{{module.name}}", "ast_source": "ast.module.identifier", "data_type": "inline_text", "fallback_value": "core.api", "required": True},
                {"placeholder": "{{api.endpoints}}", "ast_source": "ast.routers[*].endpoints", "data_type": "markdown_table", "fallback_value": "| - | - | - |", "required": True},
                {"placeholder": "{{classes.signatures}}", "ast_source": "ast.classes[*].signature", "data_type": "code_block", "fallback_value": "```python\n# No models\n```", "required": True},
                {"placeholder": "{{dependencies.graph}}", "ast_source": "ast.imports.dependencies", "data_type": "bullet_list", "fallback_value": "- None", "required": False},
            ],
            "constraints": {
                "required_sections": ["## Overview", "## Authentication & RBAC", "## Endpoints Specification", "## Data Models & Schemas"],
                "forbidden_patterns": ["TODO", "TBD", "FIXME", "example.com"],
                "tone_style": "Technical & Concise",
                "require_code_blocks": True,
                "require_tables_for_params": True,
                "max_section_words": 450,
                "enforce_strict_mode": True,
            },
        },
        {
            "name": "Standard Repository README",
            "slug": "standard-repository-readme",
            "category": "README",
            "description": "Mẫu README.md chuẩn hóa cho toàn bộ repository trong tổ chức, bao gồm kiến trúc và hướng dẫn khởi chạy.",
            "is_enforced": True,
            "target_path_pattern": "README.md",
            "content": (
                "# {{project.name}}\n\n"
                "## Project Overview\n"
                "Hệ thống quản trị và đồng bộ tài liệu kỹ thuật sống động gắn liền với vòng đời mã nguồn.\n\n"
                "## Architecture & Core Modules\n"
                "{{functions.list}}\n\n"
                "## Tech Stack & Dependencies\n"
                "{{dependencies.graph}}\n\n"
                "## Quick Start\n"
                "```bash\n"
                "uvicorn main:app --reload\n"
                "```\n"
            ),
            "mappings": [
                {"placeholder": "{{project.name}}", "ast_source": "ast.repository.name", "data_type": "inline_text", "fallback_value": "LivingDocs", "required": True},
                {"placeholder": "{{functions.list}}", "ast_source": "ast.functions[*].signature", "data_type": "bullet_list", "fallback_value": "- Core services", "required": True},
                {"placeholder": "{{dependencies.graph}}", "ast_source": "ast.imports.dependencies", "data_type": "bullet_list", "fallback_value": "- Python 3.11+", "required": True},
            ],
            "constraints": {
                "required_sections": ["## Project Overview", "## Architecture & Core Modules", "## Quick Start"],
                "forbidden_patterns": ["TODO", "TBD"],
                "tone_style": "Developer-Friendly Onboarding",
                "require_code_blocks": True,
                "require_tables_for_params": False,
                "max_section_words": 500,
                "enforce_strict_mode": True,
            },
        },
        {
            "name": "Backend Service Module Guide",
            "slug": "backend-service-module-guide",
            "category": "Module Guide",
            "description": "Tài liệu chuyên sâu cho từng service/package nội bộ, ánh xạ trực tiếp class signature và luồng hàm.",
            "is_enforced": False,
            "target_path_pattern": "docs/modules/*.md",
            "content": (
                "# Module Guide: `{{module.name}}`\n\n"
                "## Responsibility\n"
                "Mô tả trách nhiệm nghiệp vụ của module `{{module.name}}` trong hệ thống `{{project.name}}`.\n\n"
                "## Core Classes & Interfaces\n"
                "{{classes.signatures}}\n\n"
                "## Public Functions\n"
                "{{functions.list}}\n"
            ),
            "mappings": [
                {"placeholder": "{{project.name}}", "ast_source": "ast.repository.name", "data_type": "inline_text", "fallback_value": "LivingDocs", "required": True},
                {"placeholder": "{{module.name}}", "ast_source": "ast.module.identifier", "data_type": "inline_text", "fallback_value": "app.services", "required": True},
                {"placeholder": "{{classes.signatures}}", "ast_source": "ast.classes[*].signature", "data_type": "code_block", "fallback_value": "```python\npass\n```", "required": True},
                {"placeholder": "{{functions.list}}", "ast_source": "ast.functions[*].signature", "data_type": "bullet_list", "fallback_value": "- None", "required": True},
            ],
            "constraints": {
                "required_sections": ["## Responsibility", "## Core Classes & Interfaces", "## Public Functions"],
                "forbidden_patterns": ["TODO", "FIXME"],
                "tone_style": "Technical & Concise",
                "require_code_blocks": True,
                "require_tables_for_params": False,
                "max_section_words": 400,
                "enforce_strict_mode": False,
            },
        },
        {
            "name": "Engineering Onboarding Guide",
            "slug": "engineering-onboarding-guide",
            "category": "Onboarding Guide",
            "description": "Cẩm nang hội nhập dành cho kỹ sư mới tham gia dự án, tổng hợp cấu trúc repo và luồng CI/CD.",
            "is_enforced": False,
            "target_path_pattern": "docs/onboarding/*.md",
            "content": (
                "# Developer Onboarding — {{project.name}}\n\n"
                "## Welcome & Environment Setup\n"
                "Hướng dẫn cài đặt môi trường phát triển cục bộ cho dự án `{{project.name}}`.\n\n"
                "## Key Dependencies\n"
                "{{dependencies.graph}}\n\n"
                "## First Contribution Workflow\n"
                "```bash\n"
                "git checkout -b feat/your-feature\n"
                "```\n"
            ),
            "mappings": [
                {"placeholder": "{{project.name}}", "ast_source": "ast.repository.name", "data_type": "inline_text", "fallback_value": "LivingDocs", "required": True},
                {"placeholder": "{{dependencies.graph}}", "ast_source": "ast.imports.dependencies", "data_type": "bullet_list", "fallback_value": "- FastAPI & Next.js", "required": True},
            ],
            "constraints": {
                "required_sections": ["## Welcome & Environment Setup", "## Key Dependencies", "## First Contribution Workflow"],
                "forbidden_patterns": ["TBD"],
                "tone_style": "Developer-Friendly Onboarding",
                "require_code_blocks": True,
                "require_tables_for_params": False,
                "max_section_words": 600,
                "enforce_strict_mode": False,
            },
        },
        {
            "name": "Architecture Decision Record (ADR)",
            "slug": "architecture-decision-record-adr",
            "category": "ADR",
            "description": "Ghi nhận quyết định kiến trúc phần mềm gắn với Pull Request và phân tích tác động AST.",
            "is_enforced": True,
            "target_path_pattern": "docs/adr/*.md",
            "content": (
                "# ADR: Architectural Change in `{{module.name}}`\n\n"
                "## Status\n"
                "Accepted\n\n"
                "## Context\n"
                "{{adr.context}}\n\n"
                "## Decision\n"
                "{{adr.decision}}\n\n"
                "## Affected Code Entities\n"
                "{{classes.signatures}}\n"
            ),
            "mappings": [
                {"placeholder": "{{module.name}}", "ast_source": "ast.module.identifier", "data_type": "inline_text", "fallback_value": "core", "required": True},
                {"placeholder": "{{adr.context}}", "ast_source": "git.pull_request.context", "data_type": "paragraph", "fallback_value": "Context description", "required": True},
                {"placeholder": "{{adr.decision}}", "ast_source": "ast.diff.architectural_summary", "data_type": "paragraph", "fallback_value": "Decision summary", "required": True},
                {"placeholder": "{{classes.signatures}}", "ast_source": "ast.classes[*].signature", "data_type": "code_block", "fallback_value": "```python\npass\n```", "required": False},
            ],
            "constraints": {
                "required_sections": ["## Status", "## Context", "## Decision", "## Affected Code Entities"],
                "forbidden_patterns": ["TODO", "TBD", "I think", "maybe"],
                "tone_style": "Formal Architectural (ADR)",
                "require_code_blocks": True,
                "require_tables_for_params": False,
                "max_section_words": 350,
                "enforce_strict_mode": True,
            },
        },
    ]

    for item in defaults:
        tpl = DocTemplate(
            name=item["name"],
            slug=item["slug"],
            category=item["category"],
            description=item["description"],
            content=item["content"],
            placeholder_mappings_json=json.dumps(item["mappings"], ensure_ascii=False),
            formatting_constraints_json=json.dumps(item["constraints"], ensure_ascii=False),
            current_version="v1.0",
            version_number=1,
            is_enforced=item["is_enforced"],
            target_path_pattern=item["target_path_pattern"],
            is_system_default=True,
            created_by="techlead@livingdocs.io",
            updated_by="techlead@livingdocs.io",
        )
        db.add(tpl)
        db.flush()
        db.add(
            DocTemplateVersion(
                template_id=tpl.id,
                version_label="v1.0",
                version_number=1,
                content=tpl.content,
                placeholder_mappings_json=tpl.placeholder_mappings_json,
                formatting_constraints_json=tpl.formatting_constraints_json,
                change_note="Khởi tạo mẫu chuẩn hệ thống (Enterprise Baseline)",
                created_by="techlead@livingdocs.io",
            )
        )
    db.commit()


# ==============================================================================
# --- ENDPOINTS: 3.1 BUILDER, 3.2 LIBRARY & VERSIONING, 3.3 CONSTRAINTS ---
# ==============================================================================

@router.get("/placeholders/catalog")
def get_placeholder_catalog(current_user: User = Depends(get_current_user)):
    return STANDARD_AST_PLACEHOLDERS


@router.get("")
def list_templates(
    category: Optional[str] = Query(default=None),
    search: Optional[str] = Query(default=None),
    enforced_only: bool = Query(default=False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _seed_default_templates(db)
    query = db.query(DocTemplate)
    if category and category != "ALL":
        query = query.filter(DocTemplate.category == category)
    if enforced_only:
        query = query.filter(DocTemplate.is_enforced.is_(True))
    if search:
        pattern = f"%{search.strip()}%"
        query = query.filter(
            (DocTemplate.name.ilike(pattern))
            | (DocTemplate.description.ilike(pattern))
            | (DocTemplate.target_path_pattern.ilike(pattern))
        )

    templates = query.order_by(DocTemplate.is_enforced.desc(), DocTemplate.updated_at.desc()).all()
    results = []
    for t in templates:
        v_count = db.query(DocTemplateVersion).filter(DocTemplateVersion.template_id == t.id).count()
        results.append(_serialize_template(t, version_count=max(1, v_count)))
    return results


@router.get("/{template_id}")
def get_template_detail(
    template_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _seed_default_templates(db)
    tpl = db.query(DocTemplate).filter(DocTemplate.id == template_id).first()
    if not tpl:
        raise HTTPException(status_code=404, detail="Không tìm thấy template.")
    v_count = db.query(DocTemplateVersion).filter(DocTemplateVersion.template_id == tpl.id).count()
    return _serialize_template(tpl, version_count=max(1, v_count))


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(RequireRole([Role.TECH_LEAD, Role.ADMINISTRATOR]))],
)
def create_template(
    payload: TemplateCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    base_slug = _slugify(payload.name)
    slug = base_slug
    counter = 1
    while db.query(DocTemplate).filter(DocTemplate.slug == slug).first():
        counter += 1
        slug = f"{base_slug}-{counter}"

    mappings_json = json.dumps([m.model_dump() for m in payload.placeholder_mappings], ensure_ascii=False)
    constraints_json = json.dumps(payload.formatting_constraints.model_dump(), ensure_ascii=False)

    tpl = DocTemplate(
        name=payload.name.strip(),
        slug=slug,
        category=payload.category.strip(),
        description=payload.description.strip(),
        content=payload.content,
        placeholder_mappings_json=mappings_json,
        formatting_constraints_json=constraints_json,
        current_version="v1.0",
        version_number=1,
        is_enforced=payload.is_enforced,
        target_path_pattern=payload.target_path_pattern.strip() or "docs/**/*.md",
        is_system_default=False,
        created_by=current_user.email,
        updated_by=current_user.email,
    )
    db.add(tpl)
    db.flush()

    db.add(
        DocTemplateVersion(
            template_id=tpl.id,
            version_label="v1.0",
            version_number=1,
            content=tpl.content,
            placeholder_mappings_json=mappings_json,
            formatting_constraints_json=constraints_json,
            change_note=payload.change_note or "Tạo template mới",
            created_by=current_user.email,
        )
    )
    db.commit()
    db.refresh(tpl)
    return _serialize_template(tpl, version_count=1)


@router.put(
    "/{template_id}",
    dependencies=[Depends(RequireRole([Role.TECH_LEAD, Role.ADMINISTRATOR]))],
)
def update_template(
    template_id: int,
    payload: TemplateUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    tpl = db.query(DocTemplate).filter(DocTemplate.id == template_id).first()
    if not tpl:
        raise HTTPException(status_code=404, detail="Không tìm thấy template.")

    next_ver_num = tpl.version_number + 1
    next_ver_label = f"v1.{next_ver_num - 1}"

    mappings_json = json.dumps([m.model_dump() for m in payload.placeholder_mappings], ensure_ascii=False)
    constraints_json = json.dumps(payload.formatting_constraints.model_dump(), ensure_ascii=False)

    tpl.name = payload.name.strip()
    tpl.category = payload.category.strip()
    tpl.description = payload.description.strip()
    tpl.content = payload.content
    tpl.placeholder_mappings_json = mappings_json
    tpl.formatting_constraints_json = constraints_json
    tpl.version_number = next_ver_num
    tpl.current_version = next_ver_label
    tpl.is_enforced = payload.is_enforced
    tpl.target_path_pattern = payload.target_path_pattern.strip() or tpl.target_path_pattern
    tpl.updated_by = current_user.email
    tpl.updated_at = datetime.now(timezone.utc)

    db.add(
        DocTemplateVersion(
            template_id=tpl.id,
            version_label=next_ver_label,
            version_number=next_ver_num,
            content=tpl.content,
            placeholder_mappings_json=mappings_json,
            formatting_constraints_json=constraints_json,
            change_note=payload.change_note or f"Cập nhật phiên bản {next_ver_label}",
            created_by=current_user.email,
        )
    )
    db.commit()
    db.refresh(tpl)
    v_count = db.query(DocTemplateVersion).filter(DocTemplateVersion.template_id == tpl.id).count()
    return _serialize_template(tpl, version_count=v_count)


@router.post(
    "/{template_id}/clone",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(RequireRole([Role.TECH_LEAD, Role.ADMINISTRATOR]))],
)
def clone_template(
    template_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    source = db.query(DocTemplate).filter(DocTemplate.id == template_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="Không tìm thấy template nguồn để nhân bản.")

    clone_name = f"{source.name} (Clone)"
    base_slug = _slugify(clone_name)
    slug = base_slug
    counter = 1
    while db.query(DocTemplate).filter(DocTemplate.slug == slug).first():
        counter += 1
        slug = f"{base_slug}-{counter}"

    cloned = DocTemplate(
        name=clone_name,
        slug=slug,
        category=source.category,
        description=f"Nhân bản từ '{source.name}' ({source.current_version}). {source.description}",
        content=source.content,
        placeholder_mappings_json=source.placeholder_mappings_json,
        formatting_constraints_json=source.formatting_constraints_json,
        current_version="v1.0",
        version_number=1,
        is_enforced=False,
        target_path_pattern=source.target_path_pattern,
        is_system_default=False,
        created_by=current_user.email,
        updated_by=current_user.email,
    )
    db.add(cloned)
    db.flush()

    db.add(
        DocTemplateVersion(
            template_id=cloned.id,
            version_label="v1.0",
            version_number=1,
            content=cloned.content,
            placeholder_mappings_json=cloned.placeholder_mappings_json,
            formatting_constraints_json=cloned.formatting_constraints_json,
            change_note=f"Nhân bản từ template #{source.id} ({source.name})",
            created_by=current_user.email,
        )
    )
    db.commit()
    db.refresh(cloned)
    return _serialize_template(cloned, version_count=1)


@router.patch(
    "/{template_id}/enforce",
    dependencies=[Depends(RequireRole([Role.TECH_LEAD, Role.ADMINISTRATOR]))],
)
def toggle_template_enforcement(
    template_id: int,
    payload: EnforceToggleRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    tpl = db.query(DocTemplate).filter(DocTemplate.id == template_id).first()
    if not tpl:
        raise HTTPException(status_code=404, detail="Không tìm thấy template.")

    tpl.is_enforced = payload.is_enforced
    if payload.target_path_pattern is not None and payload.target_path_pattern.strip():
        tpl.target_path_pattern = payload.target_path_pattern.strip()
    tpl.updated_by = current_user.email
    tpl.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(tpl)
    v_count = db.query(DocTemplateVersion).filter(DocTemplateVersion.template_id == tpl.id).count()
    return _serialize_template(tpl, version_count=v_count)


@router.delete(
    "/{template_id}",
    dependencies=[Depends(RequireRole([Role.TECH_LEAD, Role.ADMINISTRATOR]))],
)
def delete_template(
    template_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    tpl = db.query(DocTemplate).filter(DocTemplate.id == template_id).first()
    if not tpl:
        raise HTTPException(status_code=404, detail="Không tìm thấy template.")
    db.delete(tpl)
    db.commit()
    return {"message": f"Đã xóa template '{tpl.name}' thành công."}


# --- 3.2 VERSION CONTROL & ROLLBACK ---

@router.get("/{template_id}/versions")
def list_template_versions(
    template_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    versions = (
        db.query(DocTemplateVersion)
        .filter(DocTemplateVersion.template_id == template_id)
        .order_by(DocTemplateVersion.version_number.desc())
        .all()
    )
    return [
        {
            "id": v.id,
            "template_id": v.template_id,
            "version_label": v.version_label,
            "version_number": v.version_number,
            "content": v.content,
            "placeholder_mappings": json.loads(v.placeholder_mappings_json or "[]"),
            "formatting_constraints": json.loads(v.formatting_constraints_json or "{}"),
            "change_note": v.change_note,
            "created_by": v.created_by,
            "created_at": v.created_at.isoformat() if v.created_at else None,
        }
        for v in versions
    ]


@router.post(
    "/{template_id}/rollback/{version_id}",
    dependencies=[Depends(RequireRole([Role.TECH_LEAD, Role.ADMINISTRATOR]))],
)
def rollback_template_version(
    template_id: int,
    version_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    tpl = db.query(DocTemplate).filter(DocTemplate.id == template_id).first()
    if not tpl:
        raise HTTPException(status_code=404, detail="Không tìm thấy template.")

    target_ver = (
        db.query(DocTemplateVersion)
        .filter(DocTemplateVersion.id == version_id, DocTemplateVersion.template_id == template_id)
        .first()
    )
    if not target_ver:
        raise HTTPException(status_code=404, detail="Không tìm thấy phiên bản cần khôi phục.")

    next_ver_num = tpl.version_number + 1
    next_ver_label = f"v1.{next_ver_num - 1}"

    tpl.content = target_ver.content
    tpl.placeholder_mappings_json = target_ver.placeholder_mappings_json
    tpl.formatting_constraints_json = target_ver.formatting_constraints_json
    tpl.version_number = next_ver_num
    tpl.current_version = next_ver_label
    tpl.updated_by = current_user.email
    tpl.updated_at = datetime.now(timezone.utc)

    db.add(
        DocTemplateVersion(
            template_id=tpl.id,
            version_label=next_ver_label,
            version_number=next_ver_num,
            content=tpl.content,
            placeholder_mappings_json=tpl.placeholder_mappings_json,
            formatting_constraints_json=tpl.formatting_constraints_json,
            change_note=f"Rollback về nội dung của {target_ver.version_label}",
            created_by=current_user.email,
        )
    )
    db.commit()
    db.refresh(tpl)
    v_count = db.query(DocTemplateVersion).filter(DocTemplateVersion.template_id == tpl.id).count()
    return _serialize_template(tpl, version_count=v_count)


# --- 3.1 AST PLACEHOLDER MAPPING & PREVIEW ENGINE ---

@router.post("/{template_id}/preview")
def preview_rendered_template(
    template_id: int,
    payload: PreviewTemplateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    tpl = db.query(DocTemplate).filter(DocTemplate.id == template_id).first()
    if not tpl:
        raise HTTPException(status_code=404, detail="Không tìm thấy template.")

    raw_content = payload.content if payload.content is not None else tpl.content
    mappings = (
        [m.model_dump() for m in payload.placeholder_mappings]
        if payload.placeholder_mappings is not None
        else json.loads(tpl.placeholder_mappings_json or "[]")
    )

    sample_lookup = {item["placeholder"]: item["sample_value"] for item in STANDARD_AST_PLACEHOLDERS}
    sample_lookup.update(payload.custom_ast_overrides)

    rendered = raw_content
    resolved_entities = []

    for m in mappings:
        ph = m["placeholder"]
        val = sample_lookup.get(ph) or m.get("fallback_value") or f"[{m['ast_source']}]"
        if ph in rendered:
            rendered = rendered.replace(ph, val)
            resolved_entities.append(
                {
                    "placeholder": ph,
                    "ast_source": m["ast_source"],
                    "data_type": m.get("data_type", "inline_text"),
                    "status": "bound",
                }
            )

    unresolved = re.findall(r"\{\{[a-zA-Z0-9_.-]+\}\}", rendered)
    return {
        "rendered_markdown": rendered,
        "resolved_entities": resolved_entities,
        "unresolved_placeholders": list(set(unresolved)),
    }


# --- 3.3 AI OUTPUT FORMATTING CONSTRAINTS ENFORCEMENT ENGINE ---

@router.post("/{template_id}/validate-output")
def enforce_ai_output_constraints(
    template_id: int,
    payload: ValidateAIOutputRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    tpl = db.query(DocTemplate).filter(DocTemplate.id == template_id).first()
    if not tpl:
        raise HTTPException(status_code=404, detail="Không tìm thấy template.")

    constraints = json.loads(tpl.formatting_constraints_json or "{}")
    md = payload.ai_generated_markdown

    violations: List[Dict[str, str]] = []
    passed_checks: List[str] = []

    # 1. Kiểm tra Placeholder chưa được điền dữ liệu
    leaked_placeholders = list(set(re.findall(r"\{\{[a-zA-Z0-9_.-]+\}\}", md)))
    if leaked_placeholders:
        violations.append(
            {
                "rule": "Unresolved AST Placeholders",
                "severity": "CRITICAL",
                "detail": f"Phát hiện biến chưa được ánh xạ dữ liệu: {', '.join(leaked_placeholders)}",
            }
        )
    else:
        passed_checks.append("Toàn bộ AST placeholders đã được ánh xạ dữ liệu hợp lệ.")

    # 2. Kiểm tra các Heading bắt buộc
    required_sections = constraints.get("required_sections", [])
    missing_sections = [sec for sec in required_sections if sec.strip() not in md]
    if missing_sections:
        violations.append(
            {
                "rule": "Required Headings Structure",
                "severity": "HIGH",
                "detail": f"Thiếu các đề mục bắt buộc theo chuẩn template: {', '.join(missing_sections)}",
            }
        )
    else:
        passed_checks.append(f"Đầy đủ {len(required_sections)} đề mục Markdown bắt buộc.")

    # 3. Kiểm tra từ khóa/mẫu bị cấm (Anti-Hallucination & Draft markers)
    forbidden = constraints.get("forbidden_patterns", [])
    found_forbidden = [pat for pat in forbidden if pat and re.search(re.escape(pat), md, re.IGNORECASE)]
    if found_forbidden:
        violations.append(
            {
                "rule": "Forbidden Patterns / Anti-Hallucination",
                "severity": "HIGH",
                "detail": f"Chứa cụm từ bị cấm trong tài liệu xuất bản: {', '.join(found_forbidden)}",
            }
        )
    else:
        passed_checks.append("Không chứa từ khóa nháp hoặc mẫu bị cấm (TODO/TBD/Hallucination).")

    # 4. Kiểm tra khối mã nguồn (Code Blocks)
    if constraints.get("require_code_blocks", False):
        if "```" not in md:
            violations.append(
                {
                    "rule": "Code Block Requirement",
                    "severity": "MEDIUM",
                    "detail": "Template yêu cầu ít nhất một khối mã minh họa (```language ... ```).",
                }
            )
        else:
            passed_checks.append("Đạt yêu cầu định dạng Fenced Code Block.")

    # 5. Kiểm tra bảng Markdown (Tables)
    if constraints.get("require_tables_for_params", False):
        if "| :---" not in md and "| ---" not in md and "|---" not in md:
            violations.append(
                {
                    "rule": "Markdown Table Requirement",
                    "severity": "MEDIUM",
                    "detail": "Template yêu cầu trình bày tham số/endpoint dưới dạng bảng Markdown.",
                }
            )
        else:
            passed_checks.append("Đạt yêu cầu trình bày bảng thông số Markdown Table.")

    # 6. Kiểm tra độ dài tối đa mỗi section
    max_words = int(constraints.get("max_section_words", 450))
    sections = re.split(r"\n##\s+", md)
    oversized = []
    for idx, sec_body in enumerate(sections[1:], start=1):
        lines = sec_body.strip().splitlines()
        sec_title = lines[0] if lines else f"Section #{idx}"
        word_count = len(sec_body.split())
        if word_count > max_words:
            oversized.append(f"## {sec_title} ({word_count}/{max_words} từ)")

    if oversized:
        violations.append(
            {
                "rule": "Section Verbosity Limit",
                "severity": "LOW",
                "detail": f"Các mục vượt ngưỡng {max_words} từ: {', '.join(oversized)}",
            }
        )
    else:
        passed_checks.append(f"Độ dài tất cả các mục nằm trong giới hạn <= {max_words} từ.")

    total_rules = len(violations) + len(passed_checks)
    compliance_score = round((len(passed_checks) / max(1, total_rules)) * 100)
    strict_mode = constraints.get("enforce_strict_mode", True)
    decision = "APPROVED" if len(violations) == 0 else ("BLOCKED_BY_POLICY" if strict_mode else "WARNING_ONLY")

    # Tự động chèn các đề mục còn thiếu để hỗ trợ Auto-Remediation
    remediated_md = md.rstrip()
    for sec in missing_sections:
        remediated_md += f"\n\n{sec}\n_Nội dung được bổ sung tự động theo ràng buộc của template `{tpl.name}`._\n"

    return {
        "template_id": tpl.id,
        "template_name": tpl.name,
        "enforce_strict_mode": strict_mode,
        "decision": decision,
        "compliance_score": compliance_score,
        "violations": violations,
        "passed_checks": passed_checks,
        "auto_remediated_markdown": remediated_md,
    }