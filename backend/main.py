from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from app.core.database import engine, Base, get_db
from app.core.security import get_password_hash, create_access_token, verify_password
from app.core.rbac import get_current_user, RequireRole
from app.models.user import User, Role
from pydantic import BaseModel, EmailStr

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="LivingDocs Enterprise API",
    version="2.0.0",
    description="Hệ thống RESTful API kết nối PostgreSQL với phân quyền 5 Actor"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class UserRegister(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    role: Role = Role.DEVELOPER

@app.get("/")
def read_root():
    return {"message": "LivingDocs Core Backend Enterprise (PostgreSQL) đang hoạt động thành công!"}

# --- AUTH ENDPOINTS ---
@app.post("/api/v1/auth/register", status_code=status.HTTP_201_CREATED)
def register(data: UserRegister, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == data.email).first():
        raise HTTPException(status_code=400, detail="Email này đã được đăng ký trên hệ thống!")
    
    user = User(
        email=data.email,
        hashed_password=get_password_hash(data.password),
        full_name=data.full_name,
        role=data.role
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return {
        "message": "Đăng ký tài khoản thành công",
        "user_id": user.id,
        "email": user.email,
        "role": user.role
    }

# Đăng nhập chuẩn OAuth2 Form Data
@app.post("/api/v1/auth/login")
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Email hoặc mật khẩu không chính xác!")
    
    access_token = create_access_token(data={"sub": user.id, "role": user.role.value})
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "role": user.role,
        "full_name": user.full_name
    }

@app.get("/api/v1/users/me")
def read_current_user(user: User = Depends(get_current_user)):
    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role
    }

# --- CHỨC NĂNG PHÂN QUYỀN RBAC CHO 5 ACTORS ---
@app.post("/api/v1/documents/draft", dependencies=[Depends(RequireRole([Role.DEVELOPER, Role.STAFF, Role.MANAGER, Role.TECH_LEAD, Role.ADMINISTRATOR]))])
def create_draft():
    return {"message": "Tạo bản thảo thành công (Dành cho Developer)"}

@app.post("/api/v1/workflow/review", dependencies=[Depends(RequireRole([Role.STAFF, Role.MANAGER, Role.ADMINISTRATOR]))])
def staff_review():
    return {"message": "Phê duyệt Vòng 1 thành công (Dành cho Staff Reviewer)"}

@app.post("/api/v1/workflow/approve", dependencies=[Depends(RequireRole([Role.MANAGER, Role.ADMINISTRATOR]))])
def manager_approve():
    return {"message": "Phê duyệt chung cuộc & Xuất bản (Dành cho Manager Approver)"}

@app.get("/api/v1/governance/dashboard", dependencies=[Depends(RequireRole([Role.TECH_LEAD, Role.ADMINISTRATOR]))])
def tech_lead_dashboard():
    return {"message": "Xem báo cáo sức khỏe tài liệu & Quản lý Template (Dành cho Tech Lead)"}

@app.get("/api/v1/admin/users", dependencies=[Depends(RequireRole([Role.ADMINISTRATOR]))])
def admin_get_users(db: Session = Depends(get_db)):
    users = db.query(User).all()
    return [{"id": u.id, "email": u.email, "role": u.role, "full_name": u.full_name} for u in users]