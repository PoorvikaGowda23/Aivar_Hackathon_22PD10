"""
Stage 10: Database connection and session setup.

Uses Neon Postgres (via DATABASE_URL) in production/deployment.
Falls back to SQLite for local development if DATABASE_URL is not set.
Supports overriding via DATABASE_URL environment variable.
"""

from __future__ import annotations

import os
from typing import Generator

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session

# Load .env first so DATABASE_URL is available via os.getenv
load_dotenv()

# Default to SQLite for local dev; Neon/Postgres in production
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./cards.db")

# SQLite requires check_same_thread=False; Postgres needs connect_timeout and pool settings
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {"connect_timeout": 10}

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True,
    pool_recycle=300,
)
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
