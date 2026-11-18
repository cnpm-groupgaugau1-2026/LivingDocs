from datetime import datetime, timezone
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from app.core.database import Base


class DocTemplate(Base):
    __tablename__ = "doc_templates"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    slug = Column(String(200), unique=True, index=True, nullable=False)
    category = Column(String(80), index=True, nullable=False)  # API Reference | README | Module Guide | Onboarding Guide | ADR
    description = Column(Text, default="")
    content = Column(Text, nullable=False)

    # 3.1: JSON list ánh xạ placeholder -> AST code entity
    placeholder_mappings_json = Column(Text, default="[]", nullable=False)

    # 3.3: JSON object quy tắc ràng buộc định dạng đầu ra cho AI
    formatting_constraints_json = Column(Text, default="{}", nullable=False)

    # 3.2: Quản lý phiên bản & chính sách áp đặt (Governance Enforcement)
    current_version = Column(String(20), default="v1.0", nullable=False)
    version_number = Column(Integer, default=1, nullable=False)
    is_enforced = Column(Boolean, default=False, nullable=False)
    target_path_pattern = Column(String(255), default="docs/**/*.md", nullable=False)
    is_system_default = Column(Boolean, default=False, nullable=False)

    created_by = Column(String(255), default="system@livingdocs.io")
    updated_by = Column(String(255), default="system@livingdocs.io")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class DocTemplateVersion(Base):
    __tablename__ = "doc_template_versions"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True)
    template_id = Column(Integer, ForeignKey("doc_templates.id", ondelete="CASCADE"), index=True, nullable=False)
    version_label = Column(String(20), nullable=False)
    version_number = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    placeholder_mappings_json = Column(Text, default="[]", nullable=False)
    formatting_constraints_json = Column(Text, default="{}", nullable=False)
    change_note = Column(String(500), default="Initial template version")
    created_by = Column(String(255), default="system@livingdocs.io")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))