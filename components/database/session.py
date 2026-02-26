from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from .config import get_database_settings
from urllib.parse import urlparse
from pathlib import Path
import time

from alembic import command
from alembic.config import Config

settings = get_database_settings()
db_url = settings.DATABASE_URL
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)
print(f"[DEBUG] Database URL: {db_url}")

engine = create_engine(db_url, future=True, pool_pre_ping=True)

class Base(DeclarativeBase):
    pass

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

def get_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()

def _ensure_database_exists():
    """Create the database if it doesn't exist"""
    parsed_url = urlparse(db_url)
    db_name = parsed_url.path.lstrip('/')
    
    # Build connection string to postgres database
    admin_url = db_url.replace(f"/{db_name}", "/postgres", 1)
    print(f"[DEBUG] Connecting to admin database to create application database...")
    
    max_retries = 5
    for attempt in range(max_retries):
        try:
            admin_engine = create_engine(admin_url, future=True, isolation_level="AUTOCOMMIT")
            with admin_engine.connect() as conn:
                # Check if database exists
                result = conn.execute(
                    text("SELECT 1 FROM pg_database WHERE datname = :db_name"),
                    {"db_name": db_name}
                )
                if not result.fetchone():
                    print(f"[DEBUG] Creating database '{db_name}'...")
                    conn.execute(text(f'CREATE DATABASE "{db_name}"'))
                    print(f"[DEBUG] Database '{db_name}' created successfully")
                else:
                    print(f"[DEBUG] Database '{db_name}' already exists")
            admin_engine.dispose()
            break
        except Exception as exc:
            if attempt < max_retries - 1:
                print(f"[DEBUG] Database creation attempt {attempt + 1} failed: {exc}, retrying...")
                time.sleep(2)
            else:
                print(f"[ERROR] Failed to create database after {max_retries} attempts: {exc}")
                raise

def _run_alembic_migrations():
    alembic_ini = Path(__file__).resolve().parent / "alembic.ini"
    alembic_script_location = Path(__file__).resolve().parent / "alembic"

    config = Config(str(alembic_ini))
    config.set_main_option("script_location", str(alembic_script_location))
    config.set_main_option("sqlalchemy.url", db_url)

    print("[DEBUG] Running Alembic migrations to head...")
    command.upgrade(config, "head")

def init_db():
    print(f"[DEBUG] Initializing database with URL: {db_url}")
    
    # First, ensure database exists
    _ensure_database_exists()
    
    # Then, establish connection to the application database
    max_retries = 5
    for attempt in range(max_retries):
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
                conn.commit()
            print("[DEBUG] Database connection successful")
            break
        except Exception as exc:
            if attempt < max_retries - 1:
                print(f"[DEBUG] DB connection attempt {attempt + 1} failed: {exc}, retrying...")
                time.sleep(2)
            else:
                print(f"[ERROR] DB connection failed after {max_retries} attempts: {exc}")
                raise
    
    _run_alembic_migrations()
    print("[DEBUG] Database initialization complete")

def close_db():
    engine.dispose()
