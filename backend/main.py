from app.api import auto_doc, grounding_diff
import base64
import hashlib
import hmac
import json
from datetime import datetime
from typing import Optional

import httpx
from fastapi import FastAPI, Depends, HTTPException, status, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import engine, Base, get_db
from app.core.security import get_password_hash, create_access_token, verify_password
from app.core.rbac import get_current_user, RequireRole
from app.models.user import User, Role
from app.models.integration_config import IntegrationConfig  # noqa: F401
from app.models.ai_engine_config import AiEngineConfig  # noqa: F401
from app.models.template import DocTemplate, DocTemplateVersion  # noqa: F401
from app.api.v1.templates import router as templates_router
from app.api.v1.doc_generation import router as doc_generation_router

from app.api.v1.admin_users import router as admin_users_router
from app.api.v1.admin_integrations import router as admin_integrations_router
from app.api.v1.admin_ai_config import router as admin_ai_config_router
from app.api.drift_detection import router as drift_router
from app.api.multimodal import router as multimodal_router


# ==============================================================================
# --- DATABASE MODELS (DOCUMENT & WEBHOOK INGESTION LOGS) ---
# ==============================================================================

class Document(Base):
    __tablename__ = "documents"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    content = Column(Text, default="")
    repo_full_name = Column(String(255), index=True, nullable=False)
    github_sha = Column(String(100), nullable=True)
    last_synced_at = Column(DateTime, default=datetime.utcnow)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=True)


class WebhookEventLog(Base):
    __tablename__ = "webhook_event_logs"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True)
    repo_full_name = Column(String(255), index=True, nullable=False)
    event_type = Column(String(50), default="push")
    commit_sha = Column(String(100), nullable=True)
    pusher = Column(String(150), nullable=True)
    affected_files = Column(Text, default="[]")
    status = Column(String(50), default="ingested")
    message = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


# Tự động khởi tạo toàn bộ bảng (bao gồm bảng của FE13) trong PostgreSQL khi server khởi động
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="LivingDocs Enterprise API",
    version="2.0.0",
    description="Hệ thống RESTful API kết nối PostgreSQL với phân quyền 5 Actor & GitHub Workspace",
)
app.include_router(drift_router)
app.include_router(multimodal_router)

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


class CommitDocumentRequest(BaseModel):
    repo_name: str  # Ví dụ: "tienndq546498-beep/tmttmm"
    file_path: str  # Ví dụ: "docs/Huong_dan_du_an_LivingDocs.md"
    content: str
    commit_message: str = "Update document via LivingDocs Enterprise"


class SyncRepoRequest(BaseModel):
    repo_name: str


class SimulateWebhookRequest(BaseModel):
    repo_name: str


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
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Email hoặc mật khẩu không chính xác!")

    role_val = user.role.value if hasattr(user.role, "value") else user.role
    access_token = create_access_token(data={"sub": str(user.id), "role": str(role_val)})
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "role": user.role,
        "full_name": getattr(user, "full_name", user.email),
    }


# ==============================================================================
# --- 1.1 GITHUB OAUTH ENDPOINTS ---
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
            err_desc = token_data.get("error_description", "Không lấy được token")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Lỗi kết nối GitHub OAuth: {err_desc}",
            )

        user_url = "https://api.github.com/user"
        user_headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/vnd.github+json",
        }

        async with httpx.AsyncClient() as client:
            user_res = await client.get(user_url, headers=user_headers)
            user_info = user_res.json()

        github_email = user_info.get("email") or f"{user_info.get('login')}@github.com"
        github_name = user_info.get("name") or user_info.get("login")

        user = db.query(User).filter(User.email == github_email).first()
        if not user:
            user = User(
                email=github_email,
                github_token=access_token,
                role=Role.DEVELOPER.value if hasattr(Role.DEVELOPER, "value") else "developer",
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

        user_role_str = str(user.role.value) if hasattr(user.role, "value") else str(user.role)
        jwt_token = create_access_token(data={"sub": str(user.id), "role": user_role_str})

        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/auth/success?token={jwt_token}&email={user.email}"
        )
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
app.include_router(templates_router)
app.include_router(doc_generation_router)

# ==============================================================================
# --- 1.1 & 1.2 GITHUB WORKSPACE MANAGEMENT & REPOSITORY SYNCHRONIZATION ---
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
    data: CommitDocumentRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
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
        oauth_scopes = repo_res.headers.get("X-OAuth-Scopes", "")

        if "repo" not in oauth_scopes.split(", ") and "repo" not in oauth_scopes:
            raise HTTPException(
                status_code=403,
                detail=(
                    f"Token GitHub hiện tại chỉ có quyền [{oauth_scopes or 'rỗng'}], thiếu quyền 'repo'. "
                    "Hãy bấm 'Thoát' ở góc dưới bên trái rồi bấm 'Kết nối GitHub OAuth' lại để cấp quyền ghi!"
                ),
            )

        if repo_res.status_code != 200:
            raise HTTPException(
                status_code=repo_res.status_code,
                detail=f"Không tìm thấy hoặc không có quyền truy cập repo '{repo_name}': {repo_res.text}",
            )

        repo_info = repo_res.json()
        if not repo_info.get("permissions", {}).get("push", False):
            raise HTTPException(
                status_code=403,
                detail=f"Tài khoản của bạn không có quyền ghi (push) vào repository '{repo_name}'.",
            )

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
    new_file_sha = res_data.get("content", {}).get("sha")
    file_url = res_data.get("content", {}).get("html_url")

    existing_doc = (
        db.query(Document)
        .filter(Document.repo_full_name == repo_name, Document.file_path == file_path)
        .first()
    )
    if existing_doc:
        existing_doc.content = data.content
        existing_doc.github_sha = new_file_sha
        existing_doc.last_synced_at = datetime.utcnow()
    else:
        doc_title = file_path.split("/")[-1].replace(".md", "").replace("_", " ")
        db.add(
            Document(
                title=doc_title,
                file_path=file_path,
                content=data.content,
                repo_full_name=repo_name,
                github_sha=new_file_sha,
                last_synced_at=datetime.utcnow(),
                owner_id=user.id,
            )
        )
    db.commit()

    return {
        "message": "Push tài liệu lên GitHub Workspace thành công!",
        "commit_sha": res_data.get("commit", {}).get("sha"),
        "file_url": file_url,
        "html_url": file_url,
    }


@app.get("/api/v1/github/integration-status", tags=["workspace"])
async def get_github_integration_status(
    repo_name: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Kiểm tra trạng thái kết nối GitHub App & thông tin đồng bộ của Workspace"""
    if not user.github_token:
        raise HTTPException(status_code=400, detail="Tài khoản chưa được liên kết với GitHub OAuth!")

    repo_clean = repo_name.strip().strip("/")
    headers = {
        "Authorization": f"Bearer {user.github_token}",
        "Accept": "application/vnd.github+json",
    }

    async with httpx.AsyncClient() as client:
        repo_res = await client.get(f"https://api.github.com/repos/{repo_clean}", headers=headers)
        if repo_res.status_code != 200:
            raise HTTPException(
                status_code=repo_res.status_code,
                detail="Không thể truy xuất thông tin Repository từ GitHub.",
            )
        repo_data = repo_res.json()

    synced_docs = db.query(Document).filter(Document.repo_full_name == repo_clean).all()
    last_sync = max([d.last_synced_at for d in synced_docs], default=None)

    return {
        "integration_type": "GitHub App & OAuth Sync",
        "status": "connected",
        "repo_full_name": repo_data.get("full_name"),
        "default_branch": repo_data.get("default_branch", "main"),
        "private": repo_data.get("private", False),
        "permissions": repo_data.get("permissions", {"pull": True, "push": False}),
        "synced_files_count": len(synced_docs),
        "last_synced_at": last_sync.isoformat() if last_sync else None,
    }


@app.post("/api/v1/github/sync", tags=["workspace"])
async def sync_github_repository(
    data: SyncRepoRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Quét và đồng bộ toàn bộ file Markdown (.md) từ GitHub Repository về PostgreSQL"""
    if not user.github_token:
        raise HTTPException(status_code=400, detail="Tài khoản chưa được liên kết với GitHub OAuth!")

    repo_clean = data.repo_name.strip().strip("/")
    headers = {
        "Authorization": f"Bearer {user.github_token}",
        "Accept": "application/vnd.github+json",
    }

    async with httpx.AsyncClient(timeout=20.0) as client:
        repo_res = await client.get(f"https://api.github.com/repos/{repo_clean}", headers=headers)
        if repo_res.status_code != 200:
            raise HTTPException(status_code=404, detail=f"Không tìm thấy repository '{repo_clean}'.")
        default_branch = repo_res.json().get("default_branch", "main")

        tree_url = f"https://api.github.com/repos/{repo_clean}/git/trees/{default_branch}?recursive=1"
        tree_res = await client.get(tree_url, headers=headers)
        if tree_res.status_code in (404, 409):
            raise HTTPException(
                status_code=400,
                detail="Repository đang trống (chưa có commit). Hãy tạo file README.md trước khi đồng bộ.",
            )
        if tree_res.status_code != 200:
            raise HTTPException(status_code=tree_res.status_code, detail="Lỗi khi quét cấu trúc thư mục GitHub.")

        tree_items = tree_res.json().get("tree", [])
        md_files = [
            item
            for item in tree_items
            if item.get("type") == "blob" and item.get("path", "").lower().endswith(".md")
        ][:30]

        added_count = 0
        updated_count = 0

        for item in md_files:
            file_path = item["path"]
            file_sha = item["sha"]

            existing_doc = (
                db.query(Document)
                .filter(
                    Document.repo_full_name == repo_clean,
                    Document.file_path == file_path,
                )
                .first()
            )

            if existing_doc and existing_doc.github_sha == file_sha:
                existing_doc.last_synced_at = datetime.utcnow()
                continue

            blob_res = await client.get(
                f"https://api.github.com/repos/{repo_clean}/git/blobs/{file_sha}",
                headers=headers,
            )
            if blob_res.status_code != 200:
                continue

            raw_b64 = blob_res.json().get("content", "")
            decoded_content = base64.b64decode(raw_b64).decode("utf-8", errors="replace")
            doc_title = file_path.split("/")[-1].replace(".md", "").replace("_", " ")

            if existing_doc:
                existing_doc.content = decoded_content
                existing_doc.github_sha = file_sha
                existing_doc.last_synced_at = datetime.utcnow()
                updated_count += 1
            else:
                new_doc = Document(
                    title=doc_title,
                    file_path=file_path,
                    content=decoded_content,
                    repo_full_name=repo_clean,
                    github_sha=file_sha,
                    last_synced_at=datetime.utcnow(),
                    owner_id=user.id,
                )
                db.add(new_doc)
                added_count += 1

        db.commit()

    all_docs = (
        db.query(Document)
        .filter(Document.repo_full_name == repo_clean)
        .order_by(Document.id.asc())
        .all()
    )
    return {
        "message": f"Đồng bộ thành công {len(md_files)} tài liệu Markdown từ {repo_clean}",
        "summary": {
            "total_md_files": len(md_files),
            "added": added_count,
            "updated": updated_count,
        },
        "documents": [
            {
                "id": d.id,
                "title": d.title,
                "file_path": d.file_path,
                "content": d.content,
                "github_sha": d.github_sha,
                "last_synced_at": d.last_synced_at.isoformat() if d.last_synced_at else None,
            }
            for d in all_docs
        ],
    }


@app.get("/api/v1/documents", tags=["workspace"])
def list_workspace_documents(
    repo_name: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Lấy danh sách tài liệu đã đồng bộ vào PostgreSQL theo Workspace"""
    repo_clean = repo_name.strip().strip("/")
    docs = (
        db.query(Document)
        .filter(Document.repo_full_name == repo_clean)
        .order_by(Document.id.asc())
        .all()
    )
    return [
        {
            "id": d.id,
            "title": d.title,
            "file_path": d.file_path,
            "content": d.content,
            "github_sha": d.github_sha,
            "last_synced_at": d.last_synced_at.isoformat() if d.last_synced_at else None,
        }
        for d in docs
    ]


# ==============================================================================
# --- 1.3 WEBHOOK HANDLER & REAL-TIME INGESTION PIPELINE ---
# ==============================================================================

def _verify_github_signature(secret: Optional[str], raw_body: bytes, signature_header: Optional[str]) -> bool:
    if not secret:
        return True
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    expected = "sha256=" + hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature_header)


async def _run_webhook_ingestion_pipeline(
    repo_full_name: str,
    branch: str,
    pusher: str,
    commit_sha: str,
    changed_md_paths: list[str],
    removed_md_paths: list[str],
    db: Session,
    explicit_token: Optional[str] = None,
) -> WebhookEventLog:
    """Pipeline bóc tách file Markdown từ sự kiện Push và nạp vào PostgreSQL theo thời gian thực"""
    github_token = explicit_token
    owner_id = None

    if not github_token:
        existing_doc = (
            db.query(Document)
            .filter(Document.repo_full_name == repo_full_name, Document.owner_id.isnot(None))
            .first()
        )
        if existing_doc:
            owner_user = db.query(User).filter(User.id == existing_doc.owner_id).first()
            if owner_user and owner_user.github_token:
                github_token = owner_user.github_token
                owner_id = owner_user.id

    if not github_token:
        fallback_user = db.query(User).filter(User.github_token.isnot(None)).first()
        if fallback_user:
            github_token = fallback_user.github_token
            owner_id = fallback_user.id

    ingested_files: list[str] = []

    if github_token and changed_md_paths:
        headers = {
            "Authorization": f"Bearer {github_token}",
            "Accept": "application/vnd.github+json",
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            for file_path in changed_md_paths:
                content_url = f"https://api.github.com/repos/{repo_full_name}/contents/{file_path}"
                res = await client.get(content_url, headers=headers, params={"ref": branch})
                if res.status_code != 200:
                    continue

                file_data = res.json()
                raw_b64 = file_data.get("content", "")
                file_sha = file_data.get("sha")
                decoded_content = base64.b64decode(raw_b64).decode("utf-8", errors="replace")
                doc_title = file_path.split("/")[-1].replace(".md", "").replace("_", " ")

                existing_doc = (
                    db.query(Document)
                    .filter(Document.repo_full_name == repo_full_name, Document.file_path == file_path)
                    .first()
                )
                if existing_doc:
                    existing_doc.content = decoded_content
                    existing_doc.github_sha = file_sha
                    existing_doc.last_synced_at = datetime.utcnow()
                else:
                    db.add(
                        Document(
                            title=doc_title,
                            file_path=file_path,
                            content=decoded_content,
                            repo_full_name=repo_full_name,
                            github_sha=file_sha,
                            last_synced_at=datetime.utcnow(),
                            owner_id=owner_id,
                        )
                    )
                ingested_files.append(file_path)

    for del_path in removed_md_paths:
        db.query(Document).filter(
            Document.repo_full_name == repo_full_name,
            Document.file_path == del_path,
        ).delete()

    total_affected = ingested_files + [f"-{p}" for p in removed_md_paths]
    log_entry = WebhookEventLog(
        repo_full_name=repo_full_name,
        event_type="push",
        commit_sha=(commit_sha or "")[:7],
        pusher=pusher or "github-webhook",
        affected_files=json.dumps(total_affected, ensure_ascii=False),
        status="ingested" if total_affected else "ignored",
        message=(
            f"Ingested {len(ingested_files)} file .md từ commit {(commit_sha or '')[:7]}"
            if total_affected
            else "Push không có thay đổi file Markdown (.md)"
        ),
        created_at=datetime.utcnow(),
    )
    db.add(log_entry)
    db.commit()
    db.refresh(log_entry)
    return log_entry


@app.post("/api/v1/github/webhook", tags=["workspace"])
async def handle_github_webhook(
    request: Request,
    x_github_event: Optional[str] = Header(default="push"),
    x_hub_signature_256: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    """Endpoint nhận sự kiện GitHub Webhook (ping / push) và kích hoạt Ingestion Pipeline"""
    raw_body = await request.body()
    webhook_secret = getattr(settings, "GITHUB_WEBHOOK_SECRET", None)

    if not _verify_github_signature(webhook_secret, raw_body, x_hub_signature_256):
        raise HTTPException(status_code=401, detail="Chữ ký X-Hub-Signature-256 không hợp lệ!")

    try:
        payload = json.loads(raw_body.decode("utf-8")) if raw_body else {}
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Payload JSON không hợp lệ.")

    repo_info = payload.get("repository", {})
    repo_full_name = repo_info.get("full_name", "unknown/repo")

    if x_github_event == "ping":
        log_entry = WebhookEventLog(
            repo_full_name=repo_full_name,
            event_type="ping",
            commit_sha="ping",
            pusher=payload.get("sender", {}).get("login", "github"),
            affected_files="[]",
            status="connected",
            message="Kết nối GitHub Webhook (ping) thành công!",
            created_at=datetime.utcnow(),
        )
        db.add(log_entry)
        db.commit()
        return {"message": "Pong! GitHub Webhook đã sẵn sàng.", "repo": repo_full_name}

    if x_github_event != "push":
        return {"message": f"Bỏ qua sự kiện '{x_github_event}'."}

    ref = payload.get("ref", "refs/heads/main")
    branch = ref.replace("refs/heads/", "")
    pusher = payload.get("pusher", {}).get("name") or payload.get("sender", {}).get("login", "github")
    commit_sha = payload.get("after") or payload.get("head_commit", {}).get("id", "")

    changed_md: set[str] = set()
    removed_md: set[str] = set()

    for commit in payload.get("commits", []):
        for f in commit.get("added", []) + commit.get("modified", []):
            if f.lower().endswith(".md"):
                changed_md.add(f)
                removed_md.discard(f)
        for f in commit.get("removed", []):
            if f.lower().endswith(".md"):
                removed_md.add(f)
                changed_md.discard(f)

    log_entry = await _run_webhook_ingestion_pipeline(
        repo_full_name=repo_full_name,
        branch=branch,
        pusher=pusher,
        commit_sha=commit_sha,
        changed_md_paths=list(changed_md),
        removed_md_paths=list(removed_md),
        db=db,
    )

    return {
        "message": log_entry.message,
        "status": log_entry.status,
        "commit_sha": log_entry.commit_sha,
        "affected_files": json.loads(log_entry.affected_files),
    }


@app.get("/api/v1/github/webhook/logs", tags=["workspace"])
def get_webhook_ingestion_logs(
    repo_name: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Lấy nhật ký Real-time Ingestion Pipeline của Workspace"""
    repo_clean = repo_name.strip().strip("/")
    logs = (
        db.query(WebhookEventLog)
        .filter(WebhookEventLog.repo_full_name == repo_clean)
        .order_by(WebhookEventLog.id.desc())
        .limit(8)
        .all()
    )
    return [
        {
            "id": item.id,
            "event_type": item.event_type,
            "commit_sha": item.commit_sha,
            "pusher": item.pusher,
            "affected_files": json.loads(item.affected_files or "[]"),
            "status": item.status,
            "message": item.message,
            "created_at": item.created_at.isoformat() if item.created_at else None,
        }
        for item in logs
    ]


@app.post("/api/v1/github/webhook/simulate", tags=["workspace"])
async def simulate_github_webhook_push(
    data: SimulateWebhookRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Kiểm thử & Demo Real-time Ingestion Pipeline từ commit mới nhất trên GitHub ngay trên localhost"""
    if not user.github_token:
        raise HTTPException(status_code=400, detail="Tài khoản chưa liên kết GitHub OAuth!")

    repo_clean = data.repo_name.strip().strip("/")
    headers = {
        "Authorization": f"Bearer {user.github_token}",
        "Accept": "application/vnd.github+json",
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        repo_res = await client.get(f"https://api.github.com/repos/{repo_clean}", headers=headers)
        default_branch = repo_res.json().get("default_branch", "main") if repo_res.status_code == 200 else "main"

        commits_res = await client.get(
            f"https://api.github.com/repos/{repo_clean}/commits?per_page=1",
            headers=headers,
        )
        if commits_res.status_code != 200 or not commits_res.json():
            raise HTTPException(status_code=400, detail="Không lấy được commit mới nhất từ Repository.")

        latest_commit = commits_res.json()[0]
        commit_sha = latest_commit.get("sha", "")
        pusher = (
            latest_commit.get("commit", {}).get("author", {}).get("name")
            or latest_commit.get("author", {}).get("login")
            or "github-simulate"
        )

        detail_res = await client.get(
            f"https://api.github.com/repos/{repo_clean}/commits/{commit_sha}",
            headers=headers,
        )
        files = detail_res.json().get("files", []) if detail_res.status_code == 200 else []

        changed_md = [
            f["filename"]
            for f in files
            if f.get("status") != "removed" and f.get("filename", "").lower().endswith(".md")
        ]
        removed_md = [
            f["filename"]
            for f in files
            if f.get("status") == "removed" and f.get("filename", "").lower().endswith(".md")
        ]

    log_entry = await _run_webhook_ingestion_pipeline(
        repo_full_name=repo_clean,
        branch=default_branch,
        pusher=pusher,
        commit_sha=commit_sha,
        changed_md_paths=changed_md,
        removed_md_paths=removed_md,
        db=db,
        explicit_token=user.github_token,
    )

    return {
        "message": log_entry.message,
        "status": log_entry.status,
        "commit_sha": log_entry.commit_sha,
        "affected_files": json.loads(log_entry.affected_files),
    }
app.include_router(auto_doc.router)

app.include_router(grounding_diff.router)

from app.api import review_workflow
app.include_router(review_workflow.router)

from app.api import ci_policy  # hoặc from backend.app.api import ci_policy tùy cấu trúc import hiện tại

app.include_router(ci_policy.router)

from app.api import version_audit

app.include_router(version_audit.router)

from app.api import governance_health

app.include_router(governance_health.router)

from app.api import knowledge_search

app.include_router(knowledge_search.router)