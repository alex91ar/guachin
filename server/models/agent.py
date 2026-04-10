# models/agent.py
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import String, BigInteger, Boolean, DateTime, ForeignKey, select, delete
from sqlalchemy.orm import Mapped, mapped_column, Session, selectinload

from models.basemodel import Base



class Agent(Base):
    __tablename__ = "agents"

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    ip: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    os: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    last_seen: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    user_id: Mapped[Optional[str]] = mapped_column(
        String(255),
        ForeignKey("users.id"),
        nullable=True,
    )
    scratchpad: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    debug: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    last_executed: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    def __init__(self, id: str, user_id: Optional[str]):
        self.id = id
        self.last_seen = datetime.now(timezone.utc)
        self.user_id = user_id

    @classmethod
    def all(cls, session: Session | None = None):
        return super().all(
            session=session,
            stmt=select(cls).where(cls.syscalls.any()),
            options=[
                selectinload(cls.syscalls),
            ],
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "ip": self.ip,
            "os": self.os,
            "last_seen": self.last_seen.isoformat() if self.last_seen else None,
            "user_id": self.user_id,
            "scratchpad": self.scratchpad,
            "debug": self.debug,
        }

 
    