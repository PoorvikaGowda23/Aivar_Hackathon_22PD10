"""
Stage 10: Database connection and session setup.

Uses SQLite with synchronous SQLAlchemy by default.
Supports overriding via DATABASE_URL environment variable (e.g. for PostgreSQL).
"""

from __future__ import annotations

import os
from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session

# Default to SQLite local database file
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./cards.db")

# SQLite requires check_same_thread=False for multi-threaded access (e.g. in FastAPI)
engine_kwargs = {}
if DATABASE_URL.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, **engine_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def init_db() -> None:
    """Creates all database tables if they do not exist."""
    Base.metadata.create_all(bind=engine)


def get_db() -> Generator[Session, None, None]:
    """FastAPI Dependency for database session management."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
