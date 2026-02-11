from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "OpsPilot AI"
    API_V1_STR: str = "/api/v1"
    
    POSTGRES_SERVER: str
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str
    DATABASE_URL: str | None = None
    
    GOOGLE_API_KEY: str
    GEMINI_MODEL_NAME: str = "gemini-pro"
    GEMINI_EMBEDDING_MODEL: str = "gemini-embedding-001"

    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()
