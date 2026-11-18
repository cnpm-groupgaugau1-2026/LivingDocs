from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class IntegrationProvider(str, Enum):
    GITHUB = "github"
    JIRA = "jira"
    SLACK = "slack"


class ConnectionStatus(str, Enum):
    CONNECTED = "connected"
    FAILED = "failed"
    UNCONFIGURED = "unconfigured"


class IntegrationOut(BaseModel):
    provider: IntegrationProvider
    display_name: str
    description: str
    is_enabled: bool
    config: Dict[str, Any]
    has_secret: bool
    masked_secret: str
    has_webhook_secret: bool
    masked_webhook_secret: str
    connection_status: ConnectionStatus
    status_message: Optional[str] = None
    last_tested_at: Optional[datetime] = None
    updated_by: Optional[str] = None
    updated_at: Optional[datetime] = None


class UpdateIntegrationRequest(BaseModel):
    is_enabled: bool = False
    config: Dict[str, Any] = Field(default_factory=dict)
    secret: Optional[str] = Field(None, description="API Token / Bot Token mới (để trống nếu giữ nguyên)")
    webhook_secret: Optional[str] = Field(None, description="Webhook Secret mới (để trống nếu giữ nguyên)")


class TestIntegrationRequest(BaseModel):
    config: Dict[str, Any] = Field(default_factory=dict)
    secret: Optional[str] = None


class TestIntegrationResponse(BaseModel):
    provider: IntegrationProvider
    success: bool
    connection_status: ConnectionStatus
    message: str
    details: Dict[str, Any] = Field(default_factory=dict)
    tested_at: datetime