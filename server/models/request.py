# models/request.py
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, LargeBinary, String, select
from sqlalchemy.dialects.mysql import LONGBLOB
from sqlalchemy.orm import Mapped, Session, mapped_column
from sqlalchemy.sql import func

from models.basemodel import Base


class Request(Base):
    __tablename__ = "requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    agent_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False,
    )
    content: Mapped[Optional[bytes]] = mapped_column(LargeBinary, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    response: Mapped[Optional[bytes]] = mapped_column(LONGBLOB, nullable=True)

    def __init__(self, agent_id: str, content: Optional[bytes]):
        self.agent_id = agent_id
        self.content = content

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "agent_id": self.agent_id,
            "content": self.content,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "response": self.response,
        }


    @classmethod
    def by_agent(
        cls,
        session: Session,
        agent_id: str,
        last_request_id: int,
    ) -> Optional["Request"]:
        stmt = (
            select(cls)
            .where(cls.agent_id == agent_id, cls.id > last_request_id)
            .order_by(cls.id.desc())
            .limit(1)
        )
        return session.scalar(stmt)

    @classmethod
    def by_id_session(cls, id: int, session: Session) -> Optional["Request"]:
        return session.get(cls, id)