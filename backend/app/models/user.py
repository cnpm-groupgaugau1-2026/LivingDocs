from enum import Enum
from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.sql import func

# Import Base dùng chung từ app.core.database
from app.core.database import Base


class Role(str, Enum):
    """Định nghĩa phân quyền đầy đủ cho dự án (RBAC)"""
    ADMIN = "admin"
    USER = "user"
    DEVELOPER = "developer"
    STAFF = "staff"
    MANAGER = "manager"
    TECH_LEAD = "tech_lead"
    ADMINISTRATOR = "administrator"


class User(Base):
    __tablename__ = "users"
    
    # Cho phép SQLAlchemy nạp lại định nghĩa bảng khi Uvicorn hot-reload
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    username = Column(String, unique=True, index=True, nullable=True)
    hashed_password = Column(String, nullable=True)  # Nullable cho trường hợp đăng nhập qua OAuth
    
    # Cột hỗ trợ GitHub OAuth
    github_token = Column(String, nullable=True)
    
    # Phân quyền & trạng thái
    role = Column(String, default=Role.USER.value)
    is_active = Column(Boolean, default=True)
    
    # Thời gian tạo / cập nhật
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())