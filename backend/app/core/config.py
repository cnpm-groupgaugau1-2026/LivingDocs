from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "LivingDocs Enterprise API"
    SECRET_KEY: str = "livingdocs_super_secret_jwt_key_2026_enterprise_mode"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # Hạn JWT Token: 24 giờ
    DATABASE_URL: str = "postgresql://living_admin:living_password_2026@localhost:5432/livingdocs_db"

    class Config:
        env_file = ".env"

settings = Settings()
