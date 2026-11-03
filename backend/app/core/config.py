from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=True, extra="ignore"
    )

    # Core Application
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    PROJECT_NAME: str = "CodeImpact"
    VERSION: str = "0.1.0"
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = "supersecretdevelopmentkeypleasereplaceinproduction"

    # Server Binding
    BACKEND_HOST: str = "0.0.0.0"
    BACKEND_PORT: int = 8000
    FRONTEND_PORT: int = 5173

    # CORS
    BACKEND_CORS_ORIGINS: list[str] | str = [
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
    ]

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    def assemble_cors_origins(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",") if i.strip()]
        elif isinstance(v, str) and v.startswith("["):
            import json

            try:
                res = json.loads(v)
                if isinstance(res, list):
                    return [str(item) for item in res]
                return ["http://localhost:5173", "http://localhost:3000"]
            except Exception:
                return ["http://localhost:5173", "http://localhost:3000"]
        elif isinstance(v, list):
            return [str(item) for item in v]
        return ["http://localhost:5173", "http://localhost:3000"]

    # PostgreSQL Database
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "codeimpact"
    POSTGRES_PASSWORD: str = "codeimpact_dev_password"
    POSTGRES_DB: str = "codeimpact_db"
    DATABASE_URL: str = (
        "postgresql+asyncpg://codeimpact:codeimpact_dev_password@localhost:5432/codeimpact_db"
    )
    SYNC_DATABASE_URL: str = (
        "postgresql+psycopg2://codeimpact:codeimpact_dev_password@localhost:5432/codeimpact_db"
    )

    # Redis Configuration
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_QUEUE_NAME: str = "codeimpact_analysis"

    # GitHub App Integration
    GITHUB_APP_ID: str = ""
    GITHUB_APP_PRIVATE_KEY: str = ""
    GITHUB_WEBHOOK_SECRET: str = "development_webhook_secret_key"
    GITHUB_CLIENT_ID: str = ""
    GITHUB_CLIENT_SECRET: str = ""
    GITHUB_API_BASE_URL: str = "https://api.github.com"

    # MLflow & Models
    MLFLOW_TRACKING_URI: str = "./mlruns"
    ML_MODEL_ARTIFACTS_PATH: str = "./backend/app/ml/models_store"

    # Snapshots & Sandboxed Repositories
    WORKSPACE_STORAGE_PATH: str = "/tmp/codeimpact_snapshots"


settings = Settings()
