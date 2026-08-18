"""
Stage 10: SQLAlchemy Models for Card Persistence.

Stores every generated compliance card as an immutable version record.
Every new generation increments the version counter for that agent_id.
"""

from __future__ import annotations

from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, Integer, String, Text
from database import Base


class CardVersionRecord(Base):
    """
    ORM Model for agent card version history.
    """
    __tablename__ = "card_versions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    agent_id = Column(String(100), index=True, nullable=False)
    agent_name = Column(String(200), nullable=False)
    version = Column(Integer, nullable=False, default=1)
    card_json = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    def __repr__(self) -> str:
        return f"<CardVersionRecord(agent_id='{self.agent_id}', version={self.version})>"
