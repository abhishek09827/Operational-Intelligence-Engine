from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "OpsPilot AI"
    API_V1_STR: str = "/api/v1"
    API_V2_STR: str = "/api/v2"
    
    POSTGRES_SERVER: str = "db"
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_DB: str = "opspilot"
    DATABASE_URL: str | None = None

    REDIS_HOST: str = "redis"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    
    GOOGLE_API_KEY: str = ""
    GEMINI_MODEL_NAME: str = "gemini-2.5-flash"
    GEMINI_EMBEDDING_MODEL: str = "models/gemini-embedding-001"

    # LLM Provider Configuration ("google" or "openrouter")
    LLM_PROVIDER: str = "openrouter"
    OPENROUTER_API_KEY: str | None = None
    OPENROUTER_MODEL_NAME: str = "deepseek/deepseek-v4-flash-latest"

    # Local LLM provider (Ollama)
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL_NAME: str = "qwen3:8b"

    # Triage engine
    TRIAGE_LLM_ENABLED: bool = True
    LLM_REQUEST_TIMEOUT_SECONDS: float = 30.0

    # Context-enrichment tools (Milestone 2)
    LOG_DIR: str = "logs"
    LOG_MAX_LINES: int = 200
    GITHUB_TOKEN: str = ""
    GITHUB_API_URL: str = "https://api.github.com"
    GITHUB_REPO: str = ""  # e.g. "my-org/checkout-service"
    RUNBOOK_DIR: str = "runbooks"
    RUNBOOK_TOP_K: int = 3

    # Langfuse Observability
    LANGFUSE_SECRET_KEY: str | None = None
    LANGFUSE_PUBLIC_KEY: str | None = None
    LANGFUSE_BASE_URL: str | None = None

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()

