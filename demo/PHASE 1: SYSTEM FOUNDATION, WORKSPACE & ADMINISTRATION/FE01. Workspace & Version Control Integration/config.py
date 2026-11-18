import os
from dataclasses import dataclass, field


def _env(name, default=""):
    return os.environ.get(name, default)


@dataclass
class Settings:
    github_client_id: str = field(default_factory=lambda: _env("GITHUB_CLIENT_ID"))
    github_client_secret: str = field(default_factory=lambda: _env("GITHUB_CLIENT_SECRET"))
    github_app_id: str = field(default_factory=lambda: _env("GITHUB_APP_ID"))
    github_app_private_key: str = field(default_factory=lambda: _env("GITHUB_APP_PRIVATE_KEY"))
    github_api_url: str = field(default_factory=lambda: _env("GITHUB_API_URL", "https://api.github.com"))
    github_oauth_url: str = field(default_factory=lambda: _env("GITHUB_OAUTH_URL", "https://github.com"))
    jwt_secret: str = field(default_factory=lambda: _env("FE01_JWT_SECRET", "change-me-in-production-32-bytes-min"))
    jwt_ttl_seconds: int = field(default_factory=lambda: int(_env("FE01_JWT_TTL", "3600")))
    public_base_url: str = field(default_factory=lambda: _env("FE01_PUBLIC_BASE_URL", "http://localhost:8000"))
    frontend_url: str = field(default_factory=lambda: _env("FE01_FRONTEND_URL", "http://localhost:3000"))
    db_path: str = field(default_factory=lambda: _env("FE01_DB_PATH", "fe01.sqlite3"))
    token_encryption_key: str = field(default_factory=lambda: _env("FE01_TOKEN_KEY", "change-me-token-key"))
    admin_logins: str = field(default_factory=lambda: _env("FE01_ADMIN_LOGINS"))
    lead_logins: str = field(default_factory=lambda: _env("FE01_LEAD_LOGINS"))
    oauth_scopes: str = "read:user user:email read:org"
    webhook_events: tuple = ("push", "pull_request", "release", "repository_dispatch")
    default_branches: tuple = ("main", "develop")
