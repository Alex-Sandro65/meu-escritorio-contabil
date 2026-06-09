from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List, Optional
import os


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True)

    APP_NAME: str = "ContaMax SaaS"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    SECRET_KEY: str = "dev-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # Railway injeta PORT automaticamente
    PORT: int = 8000

    DATABASE_URL: str = "postgresql+asyncpg://postgres:password@localhost:5432/contamax"
    DATABASE_SYNC_URL: str = "postgresql://postgres:password@localhost:5432/contamax"

    REDIS_URL: str = "redis://localhost:6379/0"

    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o"
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"

    # AWS S3 ou Cloudflare R2
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_REGION: str = "auto"
    S3_BUCKET: str = "contamax-uploads"
    S3_ENDPOINT_URL: Optional[str] = None   # Para Cloudflare R2

    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""

    ALLOWED_ORIGINS: str = "http://localhost:3000"

    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/1"

    SCI_API_URL: str = ""
    SCI_API_KEY: str = ""
    OMIE_APP_KEY: str = ""
    OMIE_APP_SECRET: str = ""
    CONTAAZUL_CLIENT_ID: str = ""
    CONTAAZUL_CLIENT_SECRET: str = ""

    @property
    def allowed_origins_list(self) -> List[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",")]

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"


settings = Settings()
