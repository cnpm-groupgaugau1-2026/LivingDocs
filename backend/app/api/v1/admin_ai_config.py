from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String
from sqlalchemy.orm import Session

from app.core.database import Base, get_db
from app.core.rbac import get_current_user
from app.models.user import User

router = APIRouter(prefix="/api/v1/admin/ai-config", tags=["Admin AI Config"])


# ==============================================================================
# --- DATABASE MODEL (TỰ TẠO BẢNG TRONG POSTGRESQL KHI KHỞI ĐỘNG) ---
# ==============================================================================

class AIParameterConfig(Base):
    __tablename__ = "ai_parameter_configs"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, default=1)

    # Nhóm 1: LLM Models & Generation Settings
    primary_provider = Column(String(50), default="openai", nullable=False)
    primary_model = Column(String(100), default="gpt-4o", nullable=False)
    fallback_model = Column(String(100), default="gpt-4o-mini", nullable=False)
    temperature = Column(Float, default=0.15, nullable=False)
    max_output_tokens = Column(Integer, default=4096, nullable=False)

    # Nhóm 2: Token Budget & Cost Guardrails
    daily_token_budget = Column(Integer, default=500000, nullable=False)
    monthly_token_budget = Column(Integer, default=10000000, nullable=False)
    budget_warning_percent = Column(Integer, default=80, nullable=False)
    auto_pause_on_exceed = Column(Boolean, default=True, nullable=False)
    current_daily_tokens_used = Column(Integer, default=42850, nullable=False)

    # Nhóm 3: Documentation Drift & CI/CD Gate Thresholds
    drift_alert_threshold = Column(Float, default=0.75, nullable=False)
    cicd_block_threshold = Column(Float, default=0.85, nullable=False)
    auto_sync_minor_drift = Column(Boolean, default=True, nullable=False)

    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    updated_by = Column(String(255), nullable=True)


# ==============================================================================
# --- PYDANTIC SCHEMAS ---
# ==============================================================================

class AIConfigUpdate(BaseModel):
    primary_provider: str = Field(..., min_length=1)
    primary_model: str = Field(..., min_length=1)
    fallback_model: str = Field(..., min_length=1)
    temperature: float = Field(..., ge=0.0, le=1.0)
    max_output_tokens: int = Field(..., ge=256, le=32768)

    daily_token_budget: int = Field(..., ge=1000)
    monthly_token_budget: int = Field(..., ge=10000)
    budget_warning_percent: int = Field(..., ge=10, le=100)
    auto_pause_on_exceed: bool

    drift_alert_threshold: float = Field(..., ge=0.1, le=1.0)
    cicd_block_threshold: float = Field(..., ge=0.1, le=1.0)
    auto_sync_minor_drift: bool


class AIConfigResponse(AIConfigUpdate):
    current_daily_tokens_used: int
    updated_at: Optional[datetime] = None
    updated_by: Optional[str] = None

    class Config:
        from_attributes = True


def _get_or_create_config(db: Session) -> AIParameterConfig:
    config = db.query(AIParameterConfig).filter(AIParameterConfig.id == 1).first()
    if not config:
        config = AIParameterConfig(id=1)
        db.add(config)
        db.commit()
        db.refresh(config)
    return config


# ==============================================================================
# --- ENDPOINTS (2.3 AI PARAMETER TUNING) ---
# ==============================================================================

@router.get("", response_model=AIConfigResponse)
def get_ai_config(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return _get_or_create_config(db)


@router.put("", response_model=AIConfigResponse)
def update_ai_config(
    payload: AIConfigUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    config = _get_or_create_config(db)
    for field, value in payload.model_dump().items():
        setattr(config, field, value)

    config.updated_at = datetime.now(timezone.utc)
    config.updated_by = current_user.email
    db.commit()
    db.refresh(config)
    return config


@router.post("/reset", response_model=AIConfigResponse)
def reset_ai_config(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    config = _get_or_create_config(db)
    config.primary_provider = "openai"
    config.primary_model = "gpt-4o"
    config.fallback_model = "gpt-4o-mini"
    config.temperature = 0.15
    config.max_output_tokens = 4096
    config.daily_token_budget = 500000
    config.monthly_token_budget = 10000000
    config.budget_warning_percent = 80
    config.auto_pause_on_exceed = True
    config.drift_alert_threshold = 0.75
    config.cicd_block_threshold = 0.85
    config.auto_sync_minor_drift = True
    config.updated_at = datetime.now(timezone.utc)
    config.updated_by = current_user.email
    db.commit()
    db.refresh(config)
    return config