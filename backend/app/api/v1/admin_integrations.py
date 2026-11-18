import base64
from datetime import datetime, timezone
import hashlib
import hmac
import json
import os
import secrets
from typing import Any, Dict, List, Optional, Tuple
from urllib import error as urllib_error
from urllib import request as urllib_request

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.api.v1.admin_users import require_admin
from app.models.integration_config import IntegrationConfig
from app.models.user import User
from app.schemas.admin_integrations import (
    ConnectionStatus,
    IntegrationOut,
    IntegrationProvider,
    TestIntegrationRequest,
    TestIntegrationResponse,
    UpdateIntegrationRequest,
)

router = APIRouter(prefix="/api/v1/admin/integrations", tags=["Admin - Third-Party Integrations"])

PROVIDER_METADATA: Dict[IntegrationProvider, Dict[str, Any]] = {
    IntegrationProvider.GITHUB: {
        "display_name": "GitHub Repository & Webhook",
        "description": "Đồng bộ AST code, nhận sự kiện Pull Request / Push và chặn CI/CD Merge Gate khi tài liệu bị lệch.",
        "default_config": {
            "owner_or_org": "",
            "default_branch": "main",
            "webhook_callback_url": "http://localhost:8000/api/v1/webhooks/github",
            "auto_sync_on_pr": True,
            "enforce_ci_gate": True,
        },
    },
    IntegrationProvider.JIRA: {
        "display_name": "Jira Issue & Drift Tracking",
        "description": "Tự động tạo ticket khi phát hiện Documentation Drift nghiêm trọng và liên kết trạng thái phê duyệt.",
        "default_config": {
            "base_url": "",
            "account_email": "",
            "project_key": "LDOC",
            "issue_type": "Task",
            "auto_create_drift_ticket": True,
        },
    },
    IntegrationProvider.SLACK: {
        "display_name": "Slack Workspace Notifications",
        "description": "Gửi cảnh báo Drift thời gian thực và yêu cầu duyệt tài liệu 2 cấp tới kênh của đội kỹ thuật.",
        "default_config": {
            "default_channel": "#livingdocs-alerts",
            "notify_on_drift": True,
            "notify_on_review_required": True,
            "notify_on_ci_blocked": True,
        },
    },
}


def _master_key() -> bytes:
    raw = os.getenv("INTEGRATION_ENCRYPTION_KEY") or os.getenv("SECRET_KEY") or "livingdocs-admin-secret-2026"
    return hashlib.sha256(raw.encode("utf-8")).digest()


def encrypt_secret(plain: Optional[str]) -> Optional[str]:
    if not plain or not plain.strip():
        return None
    data = plain.strip().encode("utf-8")
    key = _master_key()
    nonce = secrets.token_bytes(16)
    keystream = hashlib.pbkdf2_hmac("sha256", key, nonce, 10000, dklen=len(data))
    cipher = bytes(a ^ b for a, b in zip(data, keystream))
    mac = hmac.new(key, nonce + cipher, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(nonce + mac + cipher).decode("utf-8")


def decrypt_secret(token: Optional[str]) -> Optional[str]:
    if not token:
        return None
    try:
        raw = base64.urlsafe_b64decode(token.encode("utf-8"))
        nonce, mac, cipher = raw[:16], raw[16:48], raw[48:]
        key = _master_key()
        expected_mac = hmac.new(key, nonce + cipher, hashlib.sha256).digest()
        if not hmac.compare_digest(mac, expected_mac):
            return None
        keystream = hashlib.pbkdf2_hmac("sha256", key, nonce, 10000, dklen=len(cipher))
        return bytes(a ^ b for a, b in zip(cipher, keystream)).decode("utf-8")
    except Exception:
        return None


def mask_secret(plain: Optional[str]) -> str:
    if not plain:
        return ""
    if len(plain) <= 6:
        return "••••••"
    return f"{plain[:4]}••••••••{plain[-4:]}"


def _ensure_table_and_defaults(db: Session) -> None:
    IntegrationConfig.__table__.create(bind=db.get_bind(), checkfirst=True)
    for provider, meta in PROVIDER_METADATA.items():
        row = db.query(IntegrationConfig).filter(IntegrationConfig.provider == provider.value).first()
        if not row:
            db.add(
                IntegrationConfig(
                    provider=provider.value,
                    is_enabled=False,
                    config_json=json.dumps(meta["default_config"]),
                    connection_status=ConnectionStatus.UNCONFIGURED.value,
                )
            )
    db.commit()


def _serialize(row: IntegrationConfig) -> IntegrationOut:
    provider = IntegrationProvider(row.provider)
    meta = PROVIDER_METADATA[provider]
    try:
        saved_cfg = json.loads(row.config_json or "{}")
    except json.JSONDecodeError:
        saved_cfg = {}

    merged_cfg = {**meta["default_config"], **saved_cfg}
    plain_secret = decrypt_secret(row.encrypted_secret)
    plain_webhook = decrypt_secret(row.encrypted_webhook_secret)

    status_val = (
        ConnectionStatus(row.connection_status)
        if row.connection_status in ConnectionStatus._value2member_map_
        else ConnectionStatus.UNCONFIGURED
    )

    return IntegrationOut(
        provider=provider,
        display_name=meta["display_name"],
        description=meta["description"],
        is_enabled=row.is_enabled,
        config=merged_cfg,
        has_secret=bool(plain_secret),
        masked_secret=mask_secret(plain_secret),
        has_webhook_secret=bool(plain_webhook),
        masked_webhook_secret=mask_secret(plain_webhook),
        connection_status=status_val,
        status_message=row.status_message,
        last_tested_at=row.last_tested_at,
        updated_by=row.updated_by,
        updated_at=row.updated_at,
    )


def _http_json(
    url: str,
    method: str = "GET",
    headers: Optional[Dict[str, str]] = None,
    body: Optional[bytes] = None,
    timeout: int = 8,
) -> Tuple[int, Dict[str, Any]]:
    req = urllib_request.Request(url, data=body, method=method)
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    try:
        with urllib_request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="ignore")
            return resp.status, (json.loads(raw) if raw else {})
    except urllib_error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="ignore")
        try:
            data = json.loads(raw) if raw else {}
        except Exception:
            data = {"error": raw or str(e)}
        return e.code, data
    except Exception as e:
        return 0, {"error": str(e)}


def _verify_provider(
    provider: IntegrationProvider,
    config: Dict[str, Any],
    secret: Optional[str],
) -> Tuple[bool, str, Dict[str, Any]]:
    if not secret:
        return False, "Chưa nhập API Token / Bot Token để kiểm tra kết nối.", {}

    if provider == IntegrationProvider.GITHUB:
        code, data = _http_json(
            "https://api.github.com/user",
            headers={
                "Authorization": f"Bearer {secret}",
                "Accept": "application/vnd.github+json",
                "User-Agent": "LivingDocs-Admin",
            },
        )
        if code == 200:
            login = data.get("login", "unknown")
            return True, f"Kết nối GitHub thành công (Tài khoản: @{login}).", {"login": login, "id": data.get("id")}
        return False, f"GitHub từ chối xác thực (HTTP {code}): {data.get('message', data.get('error', 'Invalid token'))}", {}

    if provider == IntegrationProvider.JIRA:
        base_url = str(config.get("base_url") or "").strip().rstrip("/")
        email = str(config.get("account_email") or "").strip()
        if not base_url or not email:
            return False, "Vui lòng nhập đầy đủ Jira Base URL và Account Email.", {}
        basic = base64.b64encode(f"{email}:{secret}".encode("utf-8")).decode("utf-8")
        code, data = _http_json(
            f"{base_url}/rest/api/3/myself",
            headers={
                "Authorization": f"Basic {basic}",
                "Accept": "application/json",
            },
        )
        if code == 200:
            display_name = data.get("displayName", email)
            return True, f"Kết nối Jira thành công ({display_name}).", {"accountId": data.get("accountId")}
        return False, f"Jira xác thực thất bại (HTTP {code}): {data.get('errorMessages', data.get('error', 'Check URL/Token'))}", {}

    if provider == IntegrationProvider.SLACK:
        code, data = _http_json(
            "https://slack.com/api/auth.test",
            method="POST",
            headers={
                "Authorization": f"Bearer {secret}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            body=b"",
        )
        if code == 200 and data.get("ok") is True:
            team = data.get("team", "Workspace")
            bot_user = data.get("user", "bot")
            return True, f"Kết nối Slack thành công (Workspace: {team}, Bot: @{bot_user}).", {"team": team, "user": bot_user}
        return False, f"Slack xác thực thất bại: {data.get('error', f'HTTP {code}')}", {}

    return False, "Provider không được hỗ trợ.", {}


@router.get("", response_model=List[IntegrationOut])
def get_all_integrations(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    _ensure_table_and_defaults(db)
    order = [IntegrationProvider.GITHUB.value, IntegrationProvider.JIRA.value, IntegrationProvider.SLACK.value]
    rows = db.query(IntegrationConfig).all()
    row_map = {r.provider: r for r in rows}
    return [_serialize(row_map[p]) for p in order if p in row_map]


@router.put("/{provider}", response_model=IntegrationOut)
def update_integration(
    provider: IntegrationProvider,
    payload: UpdateIntegrationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    _ensure_table_and_defaults(db)
    row = db.query(IntegrationConfig).filter(IntegrationConfig.provider == provider.value).first()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy cấu hình dịch vụ.")

    meta = PROVIDER_METADATA[provider]
    try:
        current_cfg = json.loads(row.config_json or "{}")
    except json.JSONDecodeError:
        current_cfg = {}

    merged_cfg = {**meta["default_config"], **current_cfg, **(payload.config or {})}
    row.is_enabled = payload.is_enabled
    row.config_json = json.dumps(merged_cfg)

    if payload.secret and payload.secret.strip() and "••••" not in payload.secret:
        row.encrypted_secret = encrypt_secret(payload.secret)
    if payload.webhook_secret and payload.webhook_secret.strip() and "••••" not in payload.webhook_secret:
        row.encrypted_webhook_secret = encrypt_secret(payload.webhook_secret)

    row.updated_by = getattr(current_user, "email", str(current_user.id))
    row.updated_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(row)
    return _serialize(row)


@router.post("/{provider}/test", response_model=TestIntegrationResponse)
def test_integration_connection(
    provider: IntegrationProvider,
    payload: TestIntegrationRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    _ensure_table_and_defaults(db)
    row = db.query(IntegrationConfig).filter(IntegrationConfig.provider == provider.value).first()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy cấu hình dịch vụ.")

    try:
        saved_cfg = json.loads(row.config_json or "{}")
    except json.JSONDecodeError:
        saved_cfg = {}

    effective_cfg = {**saved_cfg, **(payload.config or {})}
    effective_secret = (
        payload.secret.strip()
        if payload.secret and payload.secret.strip() and "••••" not in payload.secret
        else decrypt_secret(row.encrypted_secret)
    )

    now = datetime.now(timezone.utc)
    success, message, details = _verify_provider(provider, effective_cfg, effective_secret)
    new_status = ConnectionStatus.CONNECTED if success else ConnectionStatus.FAILED

    row.connection_status = new_status.value
    row.status_message = message
    row.last_tested_at = now
    db.commit()

    return TestIntegrationResponse(
        provider=provider,
        success=success,
        connection_status=new_status,
        message=message,
        details=details,
        tested_at=now,
    )