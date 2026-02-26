from pydantic_settings import BaseSettings
import os

class DatabaseSettings(BaseSettings):
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        f"postgresql://{os.getenv('POSTGRES_USER', 'commuter')}:{os.getenv('POSTGRES_PASSWORD', 'commuter_password')}@{os.getenv('DB_HOST', 'db')}:{os.getenv('DB_PORT', '5432')}/{os.getenv('POSTGRES_DB', 'commuter_db')}",
    )
    
    class Config:
        env_file = "/app/.env"
        case_sensitive = True
        extra = "ignore"

def get_database_settings() -> DatabaseSettings:
    settings = DatabaseSettings()
    print(f"[DEBUG] DatabaseSettings loaded - DATABASE_URL: {settings.DATABASE_URL}")
    return settings
