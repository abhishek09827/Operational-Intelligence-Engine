from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "OpsPilot AI"
    API_V1_STR: str = "/api/v1"
    
    POSTGRES_SERVER: str = "db"
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_DB: str = "opspilot"
    DATABASE_URL: str | None = None
    
    GOOGLE_API_KEY: str = ""
    GEMINI_MODEL_NAME: str = "gemini-2.5-flash"
    GEMINI_EMBEDDING_MODEL: str = "models/gemini-embedding-001"

    # LLM Provider Configuration ("google" or "openrouter")
    LLM_PROVIDER: str = "openrouter"
    OPENROUTER_API_KEY: str | None = None
    OPENROUTER_MODEL_NAME: str = "deepseek/deepseek-v4-flash-latest"

    # Langfuse Observability
    LANGFUSE_SECRET_KEY: str | None = None
    LANGFUSE_PUBLIC_KEY: str | None = None
    LANGFUSE_BASE_URL: str | None = None

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()

