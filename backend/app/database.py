"""
UniMat AI — Database Engine & Session Management

PostgreSQL-backed SQLAlchemy engine, session factory, and FastAPI dependency injection.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base, Session
from typing import Generator

from app.config import get_settings

settings = get_settings()

# ─── Engine Configuration ───────────────────────────────────────────────────────
engine = create_engine(
    settings.DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

# ─── Session Factory ────────────────────────────────────────────────────────────
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# ─── Declarative Base ───────────────────────────────────────────────────────────
Base = declarative_base()


# ─── Dependency Injection ───────────────────────────────────────────────────────
def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that provides a database session per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
