# models/role.py
from __future__ import annotations

from typing import List, Optional, Iterable
import logging

from sqlalchemy import String, select, and_
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.basemodel import Base, db
from utils import sanitize


logger = logging.getLogger(__name__)


class Role(Base):
    __tablename__ = "roles"

    # ---- Columns ----
    id = db.Column(db.String(255), primary_key=True)
    description = db.Column(db.String(512), default="", nullable=False)

    # ---- Init ----
    def __init__(self, id: str, *, description: str = ""):
        self.id = sanitize(id).lower()
        self.description = description or ""

    # ---- Serialization ----
    def to_dict(self, *, include_users: bool = False, include_actions: bool = True) -> dict:
        data = {
            "id": self.id,
            "description": self.description,
        }
        if include_users:
            data["users"] = [u.id for u in (self.users or [])]
        if include_actions:
            data["actions"] = [a.id for a in (self.actions or [])]
        return data

