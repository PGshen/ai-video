from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://app:password@localhost:5432/video_workflow"
    database_sync_url: str = "postgresql+psycopg2://app:password@localhost:5432/video_workflow"
    temporal_address: str = "localhost:7233"
    temporal_task_queue: str = "video-production"
    api_key: str = "dev-api-key-change-in-prod"
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    anthropic_api_key: str = ""

    class Config:
        env_file = ".env"


settings = Settings()
