from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, model_validator


class ModelOption(BaseModel):
    id: str
    label: str
    provider: str
    context_window: str


class AiEngineConfigOut(BaseModel):
    generation_model: str
    fallback_model: str
    embedding_model: str
    temperature: float
    max_output_tokens: int

    daily_token_limit: int
    monthly_token_limit: int
    tokens_used_today: int
    tokens_used_month: int
    budget_alert_percent: int
    hard_stop_on_limit: bool

    drift_detection_threshold: float
    auto_approve_confidence: float
    rag_similarity_threshold: float

    updated_by: Optional[str] = None
    updated_at: Optional[datetime] = None

    available_generation_models: List[ModelOption]
    available_embedding_models: List[ModelOption]


class UpdateAiEngineConfigRequest(BaseModel):
    generation_model: str = Field(..., min_length=2, max_length=64)
    fallback_model: str = Field(..., min_length=2, max_length=64)
    embedding_model: str = Field(..., min_length=2, max_length=64)
    temperature: float = Field(..., ge=0.0, le=1.0)
    max_output_tokens: int = Field(..., ge=256, le=32768)

    daily_token_limit: int = Field(..., ge=1000, le=100_000_000)
    monthly_token_limit: int = Field(..., ge=1000, le=1_000_000_000)
    budget_alert_percent: int = Field(..., ge=50, le=99)
    hard_stop_on_limit: bool = True

    drift_detection_threshold: float = Field(..., ge=0.0, le=1.0)
    auto_approve_confidence: float = Field(..., ge=0.0, le=1.0)
    rag_similarity_threshold: float = Field(..., ge=0.0, le=1.0)

    @model_validator(mode="after")
    def check_monthly_vs_daily_budget(self):
        if self.monthly_token_limit < self.daily_token_limit:
            raise ValueError("Hạn mức token hàng tháng phải lớn hơn hoặc bằng hạn mức hàng ngày.")
        return self