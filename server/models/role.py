# models/role.py
from __future__ import annotations

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, selectinload

from models.basemodel import Base
from utils import sanitize


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    description: Mapped[str] = mapped_column(String(512), nullable=False, default="")

    def __init__(self, id: str, *, description: str = ""):
        self.id = sanitize(id).lower()
        self.description = description or ""

    @classmethod
    def by_id(cls, id: str, session=None):
        return super().by_id(
            sanitize(id).lower(),
            session=session,
            options=[
                selectinload(cls.actions),
                selectinload(cls.users),
            ],
        )

    @classmethod
    def by_id_with_actions(cls, id: str, session=None):
        return super().by_id(
            sanitize(id).lower(),
            session=session,
            options=[selectinload(cls.actions)],
        )

    @classmethod
    def all(cls, session=None):
        return super().all(
            session=session,
            options=[
                selectinload(cls.actions),
                selectinload(cls.users),
            ],
        )

    def to_dict(self, *, include_users: bool = False, include_actions: bool = True) -> dict:
        data = {
            "id": self.id,
            "description": self.description,
        }

        if include_users and self.is_loaded("users"):
            data["users"] = [u.id for u in self.users]

        if include_actions and self.is_loaded("actions"):
            data["actions"] = [a.id for a in self.actions]

        return data