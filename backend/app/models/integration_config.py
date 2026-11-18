from datetime import datetime, timezone
import uuid

from sqlalchemy import Boolean, Column, DateTime, String, Text
from app.models.user import User

# Tự động lấy lớp Base SQLAlchemy của dự án từ model User
Base = next(
    (cls for cls in User.__mro__[1:] if hasattr(cls, "metadata") and cls is not object),
    User.__base__,
)


class IntegrationConfig(Base):
    __tablename__ = "integration_configs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    provider = Column(String(32), unique=True, nullable=False, index=True)  # github | jira | slack
    is_enabled = Column(Boolean, default=False, nullable=False)
    config_json = Column(Text, default="{}", nullable=False)
    encrypted_secret = Column(Text, nullable=True)
    encrypted_webhook_secret = Column(Text, nullable=True)
    connection_status = Column(String(32), default="unconfigured", nullable=False)  # connected | failed | unconfigured
    status_message = Column(Text, nullable=True)
    last_tested_at = Column(DateTime(timezone=True), nullable=True)
    updated_by = Column(String(255), nullable=True)
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )