from __future__ import annotations

from typing import Optional, List, Iterable
import logging

from sqlalchemy import (
    String, Text, Table, Column, ForeignKey, select, and_
)

from models.basemodel import Base, db
from utils import sanitize, gen_key
import uuid

logger = logging.getLogger(__name__)

class Log(Base):
    """
    Permission-like action.
    - Primary key: id (normalized, lowercase)
    - Many-to-many with Role via role_actions
    """
    __tablename__ = "logs"

    # ---- Columns ----
    id = db.Column(db.String(16), primary_key=True)
    path = db.Column(db.String(255), nullable=False)
    method = db.Column(db.String(15), nullable=False)
    response = db.Column(db.Text, default="", nullable=False)
    response_code = db.Column(db.Integer, default="", nullable=False)
    log_time = db.Column(db.DateTime(timezone=True), nullable=True)
    user_id = db.Column(
        db.String(255),
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    # ---- Init ----
    def __init__(self, path:str, method:str, response:str, response_code:int, user_id:str):
        self.path = path
        self.method = method
        self.id = uuid.uuid4().hex[:16]
        self.user_id = user_id
        self.response = response
        self.response_code = response_code

    # ---- Serialization ----
    def to_dict(self) -> dict:
        data = {
            "id": self.id,
            "user": self.user_id,
            "method": self.method,
            "path": self.path,
            "response": self.response,
            "response_code": self.response_code
        }
        return data

    @classmethod
    def all(self):
        return super().all()

    @classmethod
    def all_by_user(self, user) -> dict:
        resp = super().all()
        for i in range(len(resp) - 1, -1, -1):
            if user is not None and resp[i].user_id != user:
                resp[i].delete()
        return resp