from pydantic_settings import BaseSettings
from typing import List
import os

class Settings(BaseSettings):
    # Application
    APP_NAME: str = "Multi-Agent AI Workflow System"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    
    # Database
    DATABASE_URL: str = "sqlite:///./app.db"
    
    # Groq API
    GROQ_API_KEY: str | None = None
    GROQ_MODEL: str = "llama-3-70b-versatile"
    GROQ_RATE_LIMIT: int = 70  # requests per minute
    
    # OpenAI API (optional fallback)
    OPENAI_API_KEY: str | None = None
    
    # JWT Authentication
    SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_HOURS: int = 24
    
    # Huey Background Tasks
    HUEY_IMMEDIATE: bool = False  # True = synchronous (for testing)
    
    # File Storage
    UPLOAD_DIR: str = "./uploads"
    MAX_UPLOAD_SIZE_MB: int = 50
    
    # API
    API_V1_PREFIX: str = "/api/v1"
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:8000"
    ]
    
    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"  # Ignore extra environment variables

settings = Settings()

# Create upload directory
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
