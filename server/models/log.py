# models/log.py
from __future__ import annotations

from typing import Optional
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Text, Integer, DateTime, ForeignKey, select
from sqlalchemy.orm import Mapped, mapped_column, Session

from models.basemodel import Base
from models.db import get_session

logger = logging.getLogger(__name__)


class Log(Base):
    """
    Request/response log entry.
    """
    __tablename__ = "logs"

    # ---- Columns ----
    id: Mapped[str] = mapped_column(String(16), primary_key=True)
    path: Mapped[str] = mapped_column(String(255), nullable=False)
    method: Mapped[str] = mapped_column(String(15), nullable=False)
    response: Mapped[str] = mapped_column(Text, nullable=False, default="")
    response_code: Mapped[int] = mapped_column(Integer, nullable=False)
    log_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    user_id: Mapped[Optional[str]] = mapped_column(
        String(255),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    # ---- Init ----
    def __init__(
        self,
        path: str,
        method: str,
        response: str,
        response_code: int,
        user_id: Optional[str],
    ):
        self.id = uuid.uuid4().hex[:16]
        self.path = path
        self.method = method
        self.response = response
        self.response_code = response_code
        self.user_id = user_id
        self.log_time = datetime.now(timezone.utc)

    # ---- Serialization ----
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user": self.user_id,
            "method": self.method,
            "path": self.path,
            "response": self.response,
            "response_code": self.response_code,
            "log_time": self.log_time.isoformat() if self.log_time else None,
        }
