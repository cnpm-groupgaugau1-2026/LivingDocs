import base64
import httpx
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr

from app.core.config import settings
from app.core.database import engine, Base, get_db
from app.core.security import get_password_hash, create_access_token, verify_password
from app.core.rbac import get_current_user, RequireRole
from app.models.user import User, Role
from app.models.integration_config import IntegrationConfig  # noqa: F401
from app.models.ai_engine_config import AiEngineConfig  # noqa: F401

from app.api.v1.admin_users import router as admin_users_router
from app.api.v1.admin_integrations import router as admin_integrations_router
from app.api.v1.admin_ai_config import router as admin_ai_config_router
from app.api.drift_detection import router as drift_router
from app.api.multimodal import router as multimodal_router

# Tự động khởi tạo toàn bộ bảng (bao gồm bảng của FE13) trong PostgreSQL khi server khởi động
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="LivingDocs Enterprise API",
    version="2.0.0",
    description="Hệ thống RESTful API kết nối PostgreSQL với phân quyền 5 Actor & GitHub Workspace",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==============================================================================
# --- PYDANTIC SCHEMAS ---
# ==============================================================================

class UserRegister(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    role: Role = Role.DEVELOPER


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class CommitDocumentRequest(BaseModel):
    repo_name: str  # Ví dụ: "owner/repo-name"
    file_path: str  # Ví dụ: "docs/LivingDocs_Guide.md"
    content: str
    commit_message: str = "Update document via LivingDocs Enterprise"


@app.get("/", tags=["root"])
def read_root():
    return {"message": "LivingDocs Core Backend Enterprise (PostgreSQL) đang hoạt động thành công!"}


# ==============================================================================
# --- AUTH ENDPOINTS ---
# ==============================================================================

@app.post("/api/v1/auth/register", status_code=status.HTTP_201_CREATED, tags=["auth"])
def register(data: UserRegister, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == data.email).first():
        raise HTTPException(status_code=400, detail="Email này đã được đăng ký trên hệ thống!")

    role_val = data.role.value if hasattr(data.role, "value") else str(data.role)
    user = User(
        email=data.email,
        hashed_password=get_password_hash(data.password),
        role=role_val,
    )
    if hasattr(user, "full_name"):
        setattr(user, "full_name", data.full_name)

    db.add(user)
    db.commit()
    db.refresh(user)
    return {
        "message": "Đăng ký tài khoản thành công",
        "user_id": user.id,
        "email": user.email,
        "role": user.role,
    }


@app.post("/api/v1/auth/login", tags=["auth"])
def login(data: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == data.email).first()
    if not user or not verify_password(data.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Email hoặc mật khẩu không chính xác!")

    role_str = str(user.role.value) if hasattr(user.role, "value") else str(user.role)
    access_token = create_access_token(data={"sub": str(user.id), "role": role_str})
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "role": user.role,
        "full_name": getattr(user, "full_name", user.email),
    }


# ==============================================================================
# --- GITHUB OAUTH ENDPOINTS ---
# ==============================================================================

@app.get("/api/v1/auth/github/login", tags=["auth"])
def github_login():
    github_auth_url = (
        f"https://github.com/login/oauth/authorize"
        f"?client_id={settings.GITHUB_CLIENT_ID}"
        f"&redirect_uri={settings.GITHUB_REDIRECT_URI}"
        f"&scope=repo%20user:email"
    )
    return RedirectResponse(url=github_auth_url)


@app.get("/api/v1/auth/github/callback", tags=["auth"])
async def github_callback(code: str, db: Session = Depends(get_db)):
    try:
        # 1. Đổi authorization code lấy access token từ GitHub
        token_url = "https://github.com/login/oauth/access_token"
        payload = {
            "client_id": settings.GITHUB_CLIENT_ID,
            "client_secret": settings.GITHUB_CLIENT_SECRET,
            "code": code,
            "redirect_uri": settings.GITHUB_REDIRECT_URI,
        }
        headers = {"Accept": "application/json"}

        async with httpx.AsyncClient() as client:
            response = await client.post(token_url, data=payload, headers=headers)
            token_data = response.json()

        access_token = token_data.get("access_token")
        if not access_token:
            err_desc = token_data.get("error_description", "Không lấy được access token từ GitHub")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Lỗi GitHub OAuth: {err_desc}",
            )

        # 2. Lấy thông tin user từ GitHub API
        async with httpx.AsyncClient() as client:
            user_res = await client.get(
                "https://api.github.com/user",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/json",
                },
            )
            user_info = user_res.json()

        github_email = user_info.get("email") or f"{user_info.get('login')}@github.com"
        github_name = user_info.get("name") or user_info.get("login")

        # 3. Lưu hoặc cập nhật user vào PostgreSQL
        user = db.query(User).filter(User.email == github_email).first()
        dev_role = Role.DEVELOPER.value if hasattr(Role.DEVELOPER, "value") else "developer"

        if not user:
            user = User(
                email=github_email,
                github_token=access_token,
                role=dev_role,
                is_active=True,
            )
            if hasattr(user, "full_name"):
                setattr(user, "full_name", github_name)
            if hasattr(user, "username"):
                setattr(user, "username", user_info.get("login"))
            db.add(user)
        else:
            user.github_token = access_token

        db.commit()
        db.refresh(user)

        # 4. Tạo JWT session và trả về kết quả
        user_role_str = str(user.role.value) if hasattr(user.role, "value") else str(user.role)
        jwt_token = create_access_token(data={"sub": str(user.id), "role": user_role_str})

        return {
            "token": jwt_token,
            "user": {
                "id": user.id,
                "email": user.email,
                "full_name": getattr(user, "full_name", user.email),
            },
        }
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"OAuth Callback Processing Error: {str(e)}",
        )


@app.get("/api/v1/users/me", tags=["users"])
def read_current_user(user: User = Depends(get_current_user)):
    return {
        "id": user.id,
        "email": user.email,
        "username": getattr(user, "username", None),
        "full_name": getattr(user, "full_name", user.email),
        "role": user.role,
    }


# ==============================================================================
# --- CHỨC NĂNG PHÂN QUYỀN RBAC CHO 5 ACTORS ---
# ==============================================================================

@app.post(
    "/api/v1/documents/draft",
    tags=["rbac"],
    dependencies=[
        Depends(RequireRole([Role.DEVELOPER, Role.STAFF, Role.MANAGER, Role.TECH_LEAD, Role.ADMINISTRATOR]))
    ],
)
def create_draft():
    return {"message": "Tạo bản thảo thành công (Dành cho Developer)"}


@app.post(
    "/api/v1/workflow/review",
    tags=["rbac"],
    dependencies=[Depends(RequireRole([Role.STAFF, Role.MANAGER, Role.ADMINISTRATOR]))],
)
def staff_review():
    return {"message": "Phê duyệt Vòng 1 thành công (Dành cho Staff Reviewer)"}


@app.post(
    "/api/v1/workflow/approve",
    tags=["rbac"],
    dependencies=[Depends(RequireRole([Role.MANAGER, Role.ADMINISTRATOR]))],
)
def manager_approve():
    return {"message": "Phê duyệt chung cuộc & Xuất bản (Dành cho Manager Approver)"}


@app.get(
    "/api/v1/governance/dashboard",
    tags=["rbac"],
    dependencies=[Depends(RequireRole([Role.TECH_LEAD, Role.ADMINISTRATOR]))],
)
def tech_lead_dashboard():
    return {"message": "Xem báo cáo sức khỏe tài liệu & Quản lý Template (Dành cho Tech Lead)"}


# ==============================================================================
# --- FE13: SYSTEM ADMINISTRATION & AI ENGINE CONFIGURATION (2.1, 2.2, 2.3) ---
# ==============================================================================

app.include_router(
    admin_users_router,
    dependencies=[Depends(RequireRole([Role.ADMINISTRATOR]))],
)
app.include_router(
    admin_integrations_router,
    dependencies=[Depends(RequireRole([Role.ADMINISTRATOR]))],
)
app.include_router(
    admin_ai_config_router,
    dependencies=[Depends(RequireRole([Role.ADMINISTRATOR]))],
)


# ==============================================================================
# --- GITHUB WORKSPACE MANAGEMENT ENDPOINTS ---
# ==============================================================================

@app.get("/api/v1/github/workspaces", tags=["workspace"])
async def get_github_workspaces(user: User = Depends(get_current_user)):
    """Lấy danh sách GitHub Repositories của User để làm Workspace"""
    if not user.github_token:
        raise HTTPException(status_code=400, detail="Tài khoản chưa được liên kết với GitHub OAuth!")

    async with httpx.AsyncClient() as client:
        res = await client.get(
            "https://api.github.com/user/repos?sort=updated&per_page=100",
            headers={
                "Authorization": f"Bearer {user.github_token}",
                "Accept": "application/vnd.github+json",
            },
        )

    if res.status_code != 200:
        raise HTTPException(
            status_code=res.status_code,
            detail="Không thể truy vấn danh sách Workspace từ GitHub API",
        )

    repos = res.json()
    return [
        {
            "id": repo["id"],
            "name": repo["name"],
            "full_name": repo["full_name"],
            "default_branch": repo["default_branch"],
            "private": repo["private"],
            "html_url": repo["html_url"],
        }
        for repo in repos
    ]


@app.post("/api/v1/github/commit", tags=["workspace"])
async def commit_document_to_github(
    data: CommitDocumentRequest, user: User = Depends(get_current_user)
):
    """Commit & Push trực tiếp nội dung file Markdown đang soạn thảo lên GitHub Workspace"""
    if not user.github_token:
        raise HTTPException(status_code=400, detail="Tài khoản chưa được liên kết với GitHub OAuth!")

    repo_name = data.repo_name.strip().strip("/")
    file_path = data.file_path.strip().lstrip("/")

    headers = {
        "Authorization": f"Bearer {user.github_token}",
        "Accept": "application/vnd.github+json",
    }

    async with httpx.AsyncClient() as client:
        repo_res = await client.get(f"https://api.github.com/repos/{repo_name}", headers=headers)
        if repo_res.status_code != 200:
            raise HTTPException(
                status_code=repo_res.status_code,
                detail=f"Không tìm thấy hoặc không có quyền truy cập repo '{repo_name}': {repo_res.text}",
            )

        repo_info = repo_res.json()
        default_branch = repo_info.get("default_branch", "main")
        url = f"https://api.github.com/repos/{repo_name}/contents/{file_path}"

        file_res = await client.get(url, headers=headers, params={"ref": default_branch})
        sha = file_res.json().get("sha") if file_res.status_code == 200 else None

        encoded_content = base64.b64encode(data.content.encode("utf-8")).decode("utf-8")
        payload = {
            "message": data.commit_message,
            "content": encoded_content,
            "branch": default_branch,
        }
        if sha:
            payload["sha"] = sha

        response = await client.put(url, headers=headers, json=payload)

    if response.status_code not in [200, 201]:
        raise HTTPException(
            status_code=response.status_code,
            detail=f"Lỗi Push lên GitHub: {response.text}",
        )

    res_data = response.json()
    file_url = res_data.get("content", {}).get("html_url")
    return {
        "message": "Push tài liệu lên GitHub Workspace thành công!",
        "commit_sha": res_data.get("commit", {}).get("sha"),
        "file_url": file_url,
        "html_url": file_url,
    }
from app.api.v1 import admin_ai_config
from app.db.database import Base, engine

Base.metadata.create_all(bind=engine)  # Đảm bảo bảng ai_engine_configs được tạo
app.include_router(admin_ai_config.router, prefix="/api/v1")

from app.api import review_workflow
app.include_router(review_workflow.router)

from app.api import ci_policy  # hoặc from backend.app.api import ci_policy tùy cấu trúc import hiện tại

app.include_router(ci_policy.router)