from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field
from typing import List, Optional

app = FastAPI(
    title="FE13. System Administration & AI Engine Configuration API",
    description="Hệ thống quản trị Admin cho project LivingDocs: Quản lý RBAC, Kết nối bên thứ 3 và Cấu hình tham số AI Engine.",
    version="1.0.0"
)

# =============================================================================
# DATABASE GIẢ ĐỊNH (IN-MEMORY DATABASE)
# =============================================================================

# Dữ liệu 2.1: Danh sách người dùng & Phân quyền
users_db = [
    {"id": 1, "username": "admin@livingdocs.ai", "role": "Admin", "status": "Active"},
    {"id": 2, "username": "dev_lead@livingdocs.ai", "role": "Maintainer", "status": "Active"},
    {"id": 3, "username": "writer@livingdocs.ai", "role": "Editor", "status": "Active"},
    {"id": 4, "username": "guest@livingdocs.ai", "role": "Viewer", "status": "Inactive"}
]

# Dữ liệu 2.2: Cấu hình tích hợp dịch vụ bên thứ 3
integrations_db = {
    "github_token": "ghp_16892347918237912839",
    "github_repo": "cnpm-group/livingdocs",
    "jira_domain": "codonmuadong.atlassian.net",
    "jira_api_key": "ATATT3xFfGF0xxxxxx",
    "slack_webhook": "https://hooks.slack.com/services/T00/B00/X00"
}

# Dữ liệu 2.3: Tham số cấu hình AI Engine
ai_config_db = {
    "llm_model": "gpt-4o",
    "embedding_model": "text-embedding-3-small",
    "temperature": 0.2,
    "token_budget": 50000,
    "confidence_threshold": 0.85
}


# =============================================================================
# SCHEMAS (MÔ HÌNH DỮ LIỆU ĐẦU VÀO / ĐẦU RA)
# =============================================================================

class UserSchema(BaseModel):
    username: str = Field(..., example="new_user@livingdocs.ai", description="Email / Tên đăng nhập")
    role: str = Field(..., example="Editor", description="Vai trò: Admin, Maintainer, Editor, Viewer")
    status: str = Field(default="Active", example="Active", description="Trạng thái: Active hoặc Inactive")

class ThirdPartyIntegrationSchema(BaseModel):
    github_token: str = Field(..., example="ghp_xxxxxxxxxxxx", description="Personal Access Token của GitHub")
    github_repo: str = Field(..., example="cnpm-group/livingdocs", description="Tên Repository GitHub")
    jira_domain: str = Field(..., example="codonmuadong.atlassian.net", description="Tên miền Jira Space")
    jira_api_key: str = Field(..., example="jira_api_key_secret", description="API Key của Jira")
    slack_webhook: str = Field(..., example="https://hooks.slack.com/...", description="Webhook URL thông báo Slack")

class AIConfigSchema(BaseModel):
    llm_model: str = Field(default="gpt-4o", example="gpt-4o", description="Mô hình LLM được chọn")
    embedding_model: str = Field(default="text-embedding-3-small", example="text-embedding-3-small", description="Mô hình Embedding")
    temperature: float = Field(default=0.2, ge=0.0, le=1.0, example=0.2, description="Độ sáng tạo (0.0 - 1.0)")
    token_budget: int = Field(default=50000, ge=1000, le=1000000, example=50000, description="Ngân sách Token tối đa/ngày")
    confidence_threshold: float = Field(default=0.85, ge=0.0, le=1.0, example=0.85, description="Ngưỡng tin cậy tự động cập nhật")


# =============================================================================
# CÔNG VIỆC 2.1: RBAC USER & PERMISSION MANAGEMENT PANEL
# =============================================================================

@app.get("/api/v1/rbac/users", tags=["2.1 RBAC User & Permission Panel"])
def list_users():
    """1. Lấy danh sách toàn bộ người dùng và phân quyền hệ thống"""
    return {
        "code": 200,
        "message": "Lấy danh sách người dùng thành công",
        "total": len(users_db),
        "data": users_db
    }

@app.post("/api/v1/rbac/users", tags=["2.1 RBAC User & Permission Panel"], status_code=status.HTTP_201_CREATED)
def create_user(user: UserSchema):
    """2. Thêm mới người dùng và gán vai trò (Role-Based Access Control)"""
    new_id = max([u["id"] for u in users_db], default=0) + 1
    new_user = {
        "id": new_id,
        "username": user.username,
        "role": user.role,
        "status": user.status
    }
    users_db.append(new_user)
    return {
        "code": 201,
        "message": f"Tạo người dùng '{user.username}' với vai trò '{user.role}' thành công!",
        "data": new_user
    }

@app.delete("/api/v1/rbac/users/{user_id}", tags=["2.1 RBAC User & Permission Panel"])
def delete_user(user_id: int):
    """3. Xóa tài khoản người dùng khỏi hệ thống theo ID"""
    global users_db
    user_to_delete = next((u for u in users_db if u["id"] == user_id), None)
    if not user_to_delete:
        raise HTTPException(status_code=404, detail="Không tìm thấy ID người dùng này")
    
    users_db = [u for u in users_db if u["id"] != user_id]
    return {
        "code": 200,
        "message": f"Đã xóa thành công người dùng ID {user_id}"
    }


# =============================================================================
# CÔNG VIỆC 2.2: THIRD-PARTY SERVICE INTEGRATION SETTINGS
# =============================================================================

@app.get("/api/v1/integrations", tags=["2.2 Third-Party Service Integrations"])
def get_third_party_settings():
    """1. Xem thông tin cấu hình kết nối GitHub, Jira và Slack hiện tại"""
    return {
        "code": 200,
        "message": "Lấy thông tin cấu hình dịch vụ thành công",
        "data": integrations_db
    }

@app.put("/api/v1/integrations", tags=["2.2 Third-Party Service Integrations"])
def update_third_party_settings(config: ThirdPartyIntegrationSchema):
    """2. Cập nhật thiết lập Token và Webhook kết nối bên thứ 3"""
    global integrations_db
    integrations_db = config.dict()
    return {
        "code": 200,
        "message": "Đã cập nhật tích hợp GitHub, Jira, Slack thành công!",
        "data": integrations_db
    }


# =============================================================================
# CÔNG VIỆC 2.3: AI PARAMETER TUNING PANEL
# =============================================================================

@app.get("/api/v1/ai-config", tags=["2.3 AI Parameter Tuning Panel"])
def get_ai_parameters():
    """1. Lấy thông số cấu hình AI Engine hiện tại"""
    return {
        "code": 200,
        "message": "Lấy thông số AI Engine thành công",
        "data": ai_config_db
    }

@app.post("/api/v1/ai-config", tags=["2.3 AI Parameter Tuning Panel"])
def update_ai_parameters(config: AIConfigSchema):
    """2. Điều chỉnh các tham số AI Engine (LLM Model, Token Budget, Thresholds)"""
    global ai_config_db
    ai_config_db = config.dict()
    return {
        "code": 200,
        "message": "Cấu hình AI Engine đã được lưu và áp dụng thành công!",
        "data": ai_config_db
    }