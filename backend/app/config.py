from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://app:password@localhost:5432/video_workflow"
    DATABASE_SYNC_URL: str = "postgresql+psycopg2://app:password@localhost:5432/video_workflow"
    TEMPORAL_ADDRESS: str = "localhost:7233"
    TEMPORAL_TASK_QUEUE: str = "video-production"
    API_KEY: str = "dev-api-key-change-in-prod"
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    ANTHROPIC_API_KEY: str = ""
    AI_PROVIDER: str = "deepseek"
    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com"
    DEEPSEEK_MODEL: str = "deepseek-v4-flash"
    DEEPSEEK_TIMEOUT_SECONDS: float = 60.0
    DEEPSEEK_SCRIPT_MAX_TOKENS: int = 8192
    DEEPSEEK_JSON_MAX_TOKENS: int = 4096
    CORS_ORIGINS: list[str] = ["http://localhost:5173"]

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
