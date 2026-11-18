from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    PROJECT_NAME: str = "LivingDocs Enterprise"

    # Cấu hình Cơ sở dữ liệu (mặc định cổng 5433)
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5433/livingdocs"

    # Cấu hình JWT Security
    SECRET_KEY: str = "super_secret_jwt_key_livingdocs_2026_change_in_prod"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    # Cấu hình GitHub OAuth
    GITHUB_CLIENT_ID: str = ""
    GITHUB_CLIENT_SECRET: str = ""
    GITHUB_REDIRECT_URI: str = "http://localhost:8000/api/v1/auth/github/callback"
    FRONTEND_URL: str = "http://localhost:3000"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()