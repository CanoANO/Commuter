from pydantic_settings import BaseSettings
from functools import lru_cache
import os

class Settings(BaseSettings):
    FLASK_ENV: str = "development"
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        f"postgresql://{os.getenv('POSTGRES_USER', 'commuter')}:{os.getenv('POSTGRES_PASSWORD', 'commuter_password')}@{os.getenv('DB_HOST', 'db')}:{os.getenv('DB_PORT', '5432')}/{os.getenv('POSTGRES_DB', 'commuter_db')}",
    )
    REDIS_URL: str = os.getenv("REDIS_URL", f"redis://{os.getenv('REDIS_HOST', 'redis')}:{os.getenv('REDIS_PORT', '6379')}/0")
    LOG_LEVEL: str = "INFO"
    GOOGLE_MAPS_API_KEY: str = ""
    
    class Config:
        env_file = "/app/.env"
        case_sensitive = True
        extra = "ignore"
    
    @property
    def DEBUG(self) -> bool:
        return self.FLASK_ENV == "development"

@lru_cache()
def get_settings() -> Settings:
    settings = Settings()
    print(f"[DEBUG] Settings loaded - DATABASE_URL: {settings.DATABASE_URL}")
    return settings
