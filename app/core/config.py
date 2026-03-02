from pydantic_settings import BaseSettings
from pydantic import Field

class Settings(BaseSettings):
    PROJECT_NAME: str = "OpsPilot AI"
    API_V1_STR: str = "/api/v1"
    
    POSTGRES_SERVER: str
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str
    DATABASE_URL: str | None = None
    
    GOOGLE_API_KEY: str = Field(default="", description="Google API key for Gemini")
    GEMINI_MODEL_NAME: str = Field(default="gemini-pro", description="Gemini model name")
    GEMINI_EMBEDDING_MODEL: str = Field(default="gemini-embedding-001", description="Gemini embedding model name")

    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"  # Ignore extra fields like LANGFUSE variables

settings = Settings()
