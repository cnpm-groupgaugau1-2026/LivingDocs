from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, EmailStr, Field


class UserRole(str, Enum):
    DEVELOPER = "developer"
    STAFF = "staff"
    MANAGER = "manager"
    TECH_LEAD = "tech_lead"
    ADMINISTRATOR = "administrator"


class UserStatus(str, Enum):
    ACTIVE = "active"
    INVITED = "invited"
    SUSPENDED = "suspended"


class AdminUserOut(BaseModel):
    id: str
    email: str
    full_name: str
    role: UserRole
    status: UserStatus
    last_active_at: Optional[datetime] = None
    created_at: Optional[datetime] = None


class UserSummaryStats(BaseModel):
    total_users: int
    active_users: int
    admin_count: int
    invited_count: int


class AdminUserListResponse(BaseModel):
    items: List[AdminUserOut]
    total: int
    page: int
    page_size: int
    stats: UserSummaryStats


class InviteUserRequest(BaseModel):
    email: EmailStr
    full_name: str = Field(..., min_length=1, max_length=150)
    role: UserRole = UserRole.DEVELOPER


class UpdateUserRoleRequest(BaseModel):
    role: UserRole


class UpdateUserStatusRequest(BaseModel):
    status: UserStatus


class RolePermissionSpec(BaseModel):
    role: UserRole
    label: str
    description: str
    permissions: Dict[str, bool]