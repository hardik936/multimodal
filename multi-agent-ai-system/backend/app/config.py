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
    
    # File Uploads
    UPLOAD_DIR: str = "uploads"
    
    # Groq API
    GROQ_API_KEY: str | None = None
    GROQ_MODEL: str = "llama-3.3-70b-versatile"
    GROQ_RATE_LIMIT: int = 70  # requests per minute
    
    # OpenAI API (optional fallback)
    OPENAI_API_KEY: str | None = None
    
    # JWT Authentication
    SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_HOURS: int = 24
    
    # Huey Background Tasks
    HUEY_IMMEDIATE: bool = False  # True = synchronous (for testing)

    # RabbitMQ
    BROKER_URL: str = "amqp://guest:guest@localhost:5672/"
    
    # File Storage
    UPLOAD_DIR: str = "./uploads"
    MAX_UPLOAD_SIZE_MB: int = 50
    
    # API
    API_V1_PREFIX: str = "/api/v1"
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:8000",
        "http://127.0.0.1:3000",
        "http://10.224.3.136:3000"
    ]
    
    # Rate Limiting & Quota Management
    RATE_LIMIT_ENABLED: bool = True
    PROVIDER_GROQ_RATE_PER_SEC: int = 50
    PROVIDER_OPENAI_RATE_PER_SEC: int = 20
    QUOTA_WINDOW_DAYS: int = 30
    DEFAULT_DAILY_QUOTA_TOKENS: int = 100000
    ROUTING_POLICY: str = "primary"  # primary|cost_weighted|latency_weighted
    PROVIDER_COOLDOWN_SEC: int = 60
    QUOTA_ENFORCEMENT: str = "soft"  # soft|hard
    REDIS_URL: str | None = None
    
    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"  # Ignore extra environment variables

settings = Settings()

# Create upload directory
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
