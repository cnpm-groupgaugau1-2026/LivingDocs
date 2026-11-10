import enum
from sqlalchemy import Column, String, Enum, Boolean, DateTime
from datetime import datetime
import uuid
from app.core.database import Base

class Role(str, enum.Enum):
    DEVELOPER = "DEVELOPER"          # Tác giả tạo/chỉnh sửa tài liệu
    STAFF = "STAFF"                  # Duyệt vòng 1 (Reviewer)
    MANAGER = "MANAGER"              # Phê duyệt vòng 2 & xuất bản (Approver)
    TECH_LEAD = "TECH_LEAD"          # Quản trị Template & Sức khỏe tài liệu
    ADMINISTRATOR = "ADMINISTRATOR"  # Quản trị toàn bộ người dùng & hệ thống

class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String, nullable=True)
    role = Column(Enum(Role), default=Role.DEVELOPER, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
