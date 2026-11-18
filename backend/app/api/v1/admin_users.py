from datetime import datetime, timezone
from typing import List, Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import Integer, func, or_
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.admin_rbac import (
    AdminUserListResponse,
    AdminUserOut,
    InviteUserRequest,
    RolePermissionSpec,
    UpdateUserRoleRequest,
    UpdateUserStatusRequest,
    UserRole,
    UserStatus,
    UserSummaryStats,
)

router = APIRouter(prefix="/api/v1/admin", tags=["Admin - RBAC & Users"])


def _raw_enum_str(val) -> str:
    if val is None:
        return ""
    return str(getattr(val, "value", val)).lower()


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    role_str = _raw_enum_str(getattr(current_user, "role", None))
    if role_str not in ("administrator", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Chỉ tài khoản Administrator mới có quyền truy cập phân hệ này.",
        )
    return current_user


def _map_db_role_to_ui(raw_val) -> UserRole:
    s = _raw_enum_str(raw_val).replace("-", "_").replace(" ", "_")
    if s in ("administrator", "admin"):
        return UserRole.ADMINISTRATOR
    if s in ("tech_lead", "techlead", "technical_lead"):
        return UserRole.TECH_LEAD
    if s == "manager":
        return UserRole.MANAGER
    if s in ("staff", "reviewer"):
        return UserRole.STAFF
    return UserRole.DEVELOPER


def _map_ui_role_to_db(ui_role: UserRole):
    col_type = getattr(User.role, "type", None)
    enum_cls = getattr(col_type, "enum_class", None)
    if enum_cls is not None:
        candidates = {
            UserRole.ADMINISTRATOR: ["ADMINISTRATOR", "ADMIN"],
            UserRole.TECH_LEAD: ["TECH_LEAD", "TECHNICAL_LEAD"],
            UserRole.MANAGER: ["MANAGER"],
            UserRole.STAFF: ["STAFF"],
            UserRole.DEVELOPER: ["DEVELOPER"],
        }[ui_role]
        for name in candidates:
            if hasattr(enum_cls, name):
                return getattr(enum_cls, name)
    return ui_role.value


def _find_user_by_id(db: Session, user_id: str) -> Optional[User]:
    if isinstance(User.id.type, Integer):
        if not user_id.isdigit():
            return None
        return db.query(User).filter(User.id == int(user_id)).first()
    return db.query(User).filter(User.id == user_id).first()


def _serialize_user(user: User) -> AdminUserOut:
    role = _map_db_role_to_ui(getattr(user, "role", None))
    raw_status = _raw_enum_str(getattr(user, "status", None))
    hashed_pw = str(getattr(user, "hashed_password", "") or "")

    if raw_status in UserStatus._value2member_map_:
        user_status = UserStatus(raw_status)
    elif hashed_pw.startswith("INVITED_"):
        user_status = UserStatus.INVITED
    elif getattr(user, "is_active", True):
        user_status = UserStatus.ACTIVE
    else:
        user_status = UserStatus.SUSPENDED

    display_name = (
        getattr(user, "full_name", None)
        or getattr(user, "name", None)
        or getattr(user, "username", None)
        or user.email.split("@")[0]
    )

    return AdminUserOut(
        id=str(user.id),
        email=user.email,
        full_name=display_name,
        role=role,
        status=user_status,
        last_active_at=getattr(user, "last_active_at", None),
        created_at=getattr(user, "created_at", None),
    )


ROLE_PERMISSION_MATRIX: List[RolePermissionSpec] = [
    RolePermissionSpec(
        role=UserRole.DEVELOPER,
        label="Developer",
        description="Tạo bản thảo tài liệu từ mã nguồn/AST, chỉnh sửa nội dung và đồng bộ GitHub Workspace.",
        permissions={
            "view_docs": True,
            "create_draft": True,
            "review_tier1": False,
            "approve_publish": False,
            "governance_template": False,
            "manage_rbac_users": False,
            "configure_ai_integrations": False,
        },
    ),
    RolePermissionSpec(
        role=UserRole.STAFF,
        label="Staff",
        description="Kiểm tra kỹ thuật, đối chiếu bằng chứng Diff và phê duyệt Vòng 1 (Staff Reviewer).",
        permissions={
            "view_docs": True,
            "create_draft": True,
            "review_tier1": True,
            "approve_publish": False,
            "governance_template": False,
            "manage_rbac_users": False,
            "configure_ai_integrations": False,
        },
    ),
    RolePermissionSpec(
        role=UserRole.MANAGER,
        label="Manager",
        description="Phê duyệt chung cuộc, ký duyệt xuất bản tài liệu chính thức (Manager Approver).",
        permissions={
            "view_docs": True,
            "create_draft": True,
            "review_tier1": True,
            "approve_publish": True,
            "governance_template": False,
            "manage_rbac_users": False,
            "configure_ai_integrations": False,
        },
    ),
    RolePermissionSpec(
        role=UserRole.TECH_LEAD,
        label="Technical Lead",
        description="Giám sát sức khỏe tri thức toàn dự án, quản lý chuẩn Template và kiểm soát Drift.",
        permissions={
            "view_docs": True,
            "create_draft": True,
            "review_tier1": False,
            "approve_publish": False,
            "governance_template": True,
            "manage_rbac_users": False,
            "configure_ai_integrations": False,
        },
    ),
    RolePermissionSpec(
        role=UserRole.ADMINISTRATOR,
        label="Administrator",
        description="Toàn quyền quản trị hệ thống, phân quyền 5 Actor RBAC, cấu hình tích hợp và AI Engine.",
        permissions={
            "view_docs": True,
            "create_draft": True,
            "review_tier1": True,
            "approve_publish": True,
            "governance_template": True,
            "manage_rbac_users": True,
            "configure_ai_integrations": True,
        },
    ),
]


@router.get("/roles/permissions", response_model=List[RolePermissionSpec])
def get_role_permission_matrix(_: User = Depends(require_admin)):
    return ROLE_PERMISSION_MATRIX


@router.get("/users", response_model=AdminUserListResponse)
def list_users(
    search: Optional[str] = Query(None),
    role: Optional[UserRole] = Query(None),
    user_status: Optional[UserStatus] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    query = db.query(User).order_by(User.id.asc())
    if search:
        pattern = f"%{search.strip()}%"
        filters = [User.email.ilike(pattern)]
        if hasattr(User, "full_name"):
            filters.append(User.full_name.ilike(pattern))
        query = query.filter(or_(*filters))

    all_matching = [_serialize_user(u) for u in query.all()]
    if role:
        all_matching = [u for u in all_matching if u.role == role]
    if user_status:
        all_matching = [u for u in all_matching if u.status == user_status]

    total = len(all_matching)
    start = (page - 1) * page_size
    paged_items = all_matching[start : start + page_size]

    serialized_all = [_serialize_user(u) for u in db.query(User).all()]
    stats = UserSummaryStats(
        total_users=len(serialized_all),
        active_users=sum(1 for u in serialized_all if u.status == UserStatus.ACTIVE),
        admin_count=sum(1 for u in serialized_all if u.role == UserRole.ADMINISTRATOR),
        invited_count=sum(1 for u in serialized_all if u.status == UserStatus.INVITED),
    )

    return AdminUserListResponse(
        items=paged_items,
        total=total,
        page=page,
        page_size=page_size,
        stats=stats,
    )


@router.post("/users/invite", response_model=AdminUserOut, status_code=status.HTTP_201_CREATED)
def invite_user(
    payload: InviteUserRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    existing = db.query(User).filter(func.lower(User.email) == payload.email.lower()).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Email '{payload.email}' đã tồn tại trong hệ thống.",
        )

    user_kwargs = {"email": payload.email.lower()}
    if not isinstance(User.id.type, Integer):
        user_kwargs["id"] = str(uuid.uuid4())
    if hasattr(User, "full_name"):
        user_kwargs["full_name"] = payload.full_name.strip()
    if hasattr(User, "role"):
        user_kwargs["role"] = _map_ui_role_to_db(payload.role)
    if hasattr(User, "status"):
        user_kwargs["status"] = UserStatus.INVITED.value
    if hasattr(User, "is_active"):
        user_kwargs["is_active"] = False
    if hasattr(User, "hashed_password"):
        user_kwargs["hashed_password"] = f"INVITED_{uuid.uuid4().hex}"
    if hasattr(User, "created_at"):
        user_kwargs["created_at"] = datetime.now(timezone.utc)

    new_user = User(**user_kwargs)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return _serialize_user(new_user)


@router.patch("/users/{user_id}/role", response_model=AdminUserOut)
def update_user_role(
    user_id: str,
    payload: UpdateUserRoleRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    target = _find_user_by_id(db, user_id)
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy người dùng.")

    if str(target.id) == str(current_user.id) and payload.role != UserRole.ADMINISTRATOR:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Không thể tự hạ quyền Administrator của chính bạn.",
        )

    if _map_db_role_to_ui(target.role) == UserRole.ADMINISTRATOR and payload.role != UserRole.ADMINISTRATOR:
        admin_count = sum(1 for u in db.query(User).all() if _map_db_role_to_ui(u.role) == UserRole.ADMINISTRATOR)
        if admin_count <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Hệ thống phải duy trì tối thiểu 1 tài khoản Administrator.",
            )

    target.role = _map_ui_role_to_db(payload.role)
    db.commit()
    db.refresh(target)
    return _serialize_user(target)


@router.patch("/users/{user_id}/status", response_model=AdminUserOut)
def update_user_status(
    user_id: str,
    payload: UpdateUserStatusRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    target = _find_user_by_id(db, user_id)
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy người dùng.")

    if str(target.id) == str(current_user.id) and payload.status == UserStatus.SUSPENDED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Không thể tự khóa tài khoản đang đăng nhập.",
        )

    if hasattr(target, "status"):
        target.status = payload.status.value
    if hasattr(target, "hashed_password") and str(target.hashed_password or "").startswith("INVITED_"):
        target.hashed_password = str(target.hashed_password).replace("INVITED_", "", 1)
    if hasattr(target, "is_active"):
        target.is_active = payload.status == UserStatus.ACTIVE

    db.commit()
    db.refresh(target)
    return _serialize_user(target)