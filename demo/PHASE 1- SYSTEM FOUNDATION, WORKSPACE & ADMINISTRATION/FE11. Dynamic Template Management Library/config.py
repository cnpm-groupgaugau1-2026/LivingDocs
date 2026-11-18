import os
from dataclasses import dataclass, field


def _env(*names, default=""):
    for n in names:
        v = os.environ.get(n)
        if v:
            return v
    return default


@dataclass
class Settings:
    jwt_secret: str = field(default_factory=lambda: _env("FE11_JWT_SECRET", "FE01_JWT_SECRET", default="change-me-in-production-32-bytes-min"))
    db_path: str = field(default_factory=lambda: _env("FE11_DB_PATH", default="fe11.sqlite3"))
    service_key: str = field(default_factory=lambda: _env("FE11_SERVICE_KEY"))
    max_body_chars: int = 100000
    max_name_chars: int = 100
    max_prompt_chars: int = 4000
