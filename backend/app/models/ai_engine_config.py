from datetime import datetime, timezone
from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String
from app.models.user import User

Base = next(
    (cls for cls in User.__mro__[1:] if hasattr(cls, "metadata") and cls is not object),
    User.__base__,
)


class AiEngineConfig(Base):
    __tablename__ = "ai_engine_configs"

    id = Column(String(36), primary_key=True, default="default")

    # LLM Models & Generation
    generation_model = Column(String(64), default="gpt-4o", nullable=False)
    fallback_model = Column(String(64), default="gemini-2.5-pro", nullable=False)
    embedding_model = Column(String(64), default="text-embedding-3-large", nullable=False)
    temperature = Column(Float, default=0.2, nullable=False)
    max_output_tokens = Column(Integer, default=4096, nullable=False)

    # Token Budget & Usage Tracking
    daily_token_limit = Column(Integer, default=500000, nullable=False)
    monthly_token_limit = Column(Integer, default=10000000, nullable=False)
    tokens_used_today = Column(Integer, default=0, nullable=False)
    tokens_used_month = Column(Integer, default=0, nullable=False)
    budget_alert_percent = Column(Integer, default=80, nullable=False)
    hard_stop_on_limit = Column(Boolean, default=True, nullable=False)

    # AI Quality & Governance Thresholds (0.0 -> 1.0)
    drift_detection_threshold = Column(Float, default=0.75, nullable=False)
    auto_approve_confidence = Column(Float, default=0.90, nullable=False)
    rag_similarity_threshold = Column(Float, default=0.70, nullable=False)

    updated_by = Column(String(255), nullable=True)
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )