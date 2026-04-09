# models/action.py
from __future__ import annotations

from typing import Optional, TYPE_CHECKING
import logging

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column, Session, relationship

from models.basemodel import Base
from models.enums import HttpMethod
from utils import gen_key

if TYPE_CHECKING:
    from models.role import Role

logger = logging.getLogger(__name__)


class Action(Base):
    """
    Permission-like action.
    - Primary key: id (normalized, lowercase)
    - Many-to-many with Role via role_actions
    """
    __tablename__ = "actions"

    ACTION_ID_LENGTH = 16

    # ---- Columns ----
    id: Mapped[str] = mapped_column(String(ACTION_ID_LENGTH), primary_key=True)
    path: Mapped[str] = mapped_column(String(255), nullable=False)
    method: Mapped[str] = mapped_column(String(15), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")

    # ---- Relationships ----
    roles: Mapped[list["Role"]] = relationship(
        "Role",
        secondary="role_actions",
        back_populates="actions",
        lazy="selectin",
    )

    # ---- Init ----
    def __init__(self, path: str, method: str):
        if not path or not method:
            raise ValueError("Actions require a valid path and method.")

        if method not in HttpMethod._value2member_map_:
            raise ValueError(f"Invalid HTTP method '{method}'")

        self.path = path
        self.method = method
        self.description = f"Method {method} for path {path}."
        self.id = gen_key(path, method)

    # ---- Serialization ----
    def to_dict(self, include_roles: bool = False) -> dict:
        data = {
            "id": self.id,
            "path": self.path,
            "method": self.method,
        }

        if include_roles and self.is_loaded("roles"):
            data["roles"] = [r.id for r in self.roles]

        return data

    # ---- Queries ----
    @classmethod
    def by_path_and_method(
        cls,
        session: Session,
        path: str,
        method: str,
    ) -> Optional["Action"]:
        key = gen_key(path, method)
        return cls.by_id(key)

    @classmethod
    def get_id_length(cls) -> int:
        return cls.ACTION_ID_LENGTH

    @classmethod
    def by_id(cls,id: str) -> Optional["Action"]:
        if len(id) != cls.get_id_length():
            return None
        return super().by_id(id)