from fastapi import APIRouter, Depends
from app.core.security import RoleChecker

router = APIRouter()

# Actor 1: User / Writer
@router.post("/documents/draft", dependencies=[Depends(RoleChecker(["user", "staff", "manager", "tech_lead", "admin"]))])
def create_draft():
    return {"message": "Tạo bản thảo thành công!"}

# Actor 2: Staff
@router.post("/workflow/review", dependencies=[Depends(RoleChecker(["staff", "manager", "tech_lead", "admin"]))])
def staff_review():
    return {"message": "Đã hoàn thành kiểm duyệt (Staff Review)"}

# Actor 3: Manager
@router.post("/workflow/approve", dependencies=[Depends(RoleChecker(["manager", "tech_lead", "admin"]))])
def manager_approve():
    return {"message": "Đã phê duyệt tài liệu (Manager Approve)"}

# Actor 4: Tech Lead
@router.get("/governance/dashboard", dependencies=[Depends(RoleChecker(["tech_lead", "admin"]))])
def tech_lead_dashboard():
    return {"message": "Truy cập Dashboard Quản trị Kỹ thuật thành công"}

# Actor 5: Admin (Chỉ duy nhất Admin)
@router.get("/admin/users", dependencies=[Depends(RoleChecker(["admin"]))])
def admin_get_users():
    return {"message": "Danh sách toàn bộ người dùng trong hệ thống"}