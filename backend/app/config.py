from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://app:password@localhost:5432/video_workflow"
    DATABASE_SYNC_URL: str = "postgresql+psycopg2://app:password@localhost:5432/video_workflow"
    TEMPORAL_ADDRESS: str = "localhost:7233"
    TEMPORAL_TASK_QUEUE: str = "video-production"
    AUTH_SECRET_KEY: str = "dev-auth-secret-change-in-prod"
    AUTH_ACCESS_TOKEN_EXPIRE_MINUTES: int = 2880
    AUTH_COOKIE_NAME: str = "ai_video_session"
    AUTH_COOKIE_SECURE: bool = False
    AUTH_BOOTSTRAP_ADMIN_USERNAME: str = ""
    AUTH_BOOTSTRAP_ADMIN_PASSWORD: str = ""
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_PUBLIC_ENDPOINT: str = "localhost:9000"
    MINIO_PUBLIC_SECURE: bool = False
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    ANTHROPIC_API_KEY: str = ""
    AI_PROVIDER: str = "deepseek"
    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com"
    DEEPSEEK_MODEL: str = "deepseek-v4-flash"
    DEEPSEEK_TIMEOUT_SECONDS: float = 600.0
    DEEPSEEK_CONTENT_MAX_TOKENS: int = 100000
    DEEPSEEK_JSON_MAX_TOKENS: int = 100000
    DEEPSEEK_INPUT_COST_PER_MILLION: float = 0
    DEEPSEEK_CACHED_INPUT_COST_PER_MILLION: float = 0
    DEEPSEEK_OUTPUT_COST_PER_MILLION: float = 0
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    OPENROUTER_MODEL: str = "anthropic/claude-sonnet-4-5"
    OPENROUTER_TIMEOUT_SECONDS: float = 600.0
    OPENROUTER_CONTENT_MAX_TOKENS: int = 100000
    OPENROUTER_JSON_MAX_TOKENS: int = 100000
    OPENROUTER_SITE_URL: str = ""
    OPENROUTER_SITE_NAME: str = ""
    OPENROUTER_INPUT_COST_PER_MILLION: float = 0
    OPENROUTER_CACHED_INPUT_COST_PER_MILLION: float = 0
    OPENROUTER_OUTPUT_COST_PER_MILLION: float = 0
    GEMINI_API_KEY: str = ""
    GEMINI_BASE_URL: str = "https://generativelanguage.googleapis.com/v1beta/openai"
    GEMINI_MODEL: str = "gemini-2.5-flash"
    GEMINI_TIMEOUT_SECONDS: float = 600.0
    GEMINI_CONTENT_MAX_TOKENS: int = 100000
    GEMINI_JSON_MAX_TOKENS: int = 100000
    GEMINI_INPUT_COST_PER_MILLION: float = 0
    GEMINI_CACHED_INPUT_COST_PER_MILLION: float = 0
    GEMINI_OUTPUT_COST_PER_MILLION: float = 0
    DOUBAO_API_KEY: str = ""
    DOUBAO_BASE_URL: str = "https://ark.cn-beijing.volces.com/api/v3"
    DOUBAO_MODEL: str = "doubao-seed-evolving"
    DOUBAO_TIMEOUT_SECONDS: float = 600.0
    DOUBAO_CONTENT_MAX_TOKENS: int = 100000
    DOUBAO_JSON_MAX_TOKENS: int = 100000
    DOUBAO_INPUT_COST_PER_MILLION: float = 0
    DOUBAO_CACHED_INPUT_COST_PER_MILLION: float = 0
    DOUBAO_OUTPUT_COST_PER_MILLION: float = 0
    VOLCENGINE_TTS_API_KEY: str = ""
    VOLCENGINE_TTS_1_RESOURCE_ID: str = "seed-tts-1.0"
    VOLCENGINE_TTS_RESOURCE_ID: str = "seed-tts-2.0"
    TTS_ENGINE: str = "volcengine"
    MINIO_BUCKET: str = "video-workflow"
    MANIM_TIMEOUT_SECONDS: float = 600.0
    REMOTION_TIMEOUT_SECONDS: float = 600.0
    REMOTION_TEMPLATE_DIR: str = "remotion-template"
    AGENT_MODEL: str = "claude-opus-5"
    AGENT_MAX_TURNS: int = 40
    AGENT_MAX_BUDGET_USD: float = 2.0
    AGENT_TIMEOUT_SECONDS: float = 1800.0
    CORS_ORIGINS: list[str] = ["http://localhost:5173"]

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
