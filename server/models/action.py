# models/action.py
from __future__ import annotations

from typing import Optional
import logging


from models.basemodel import Base, db
from utils import sanitize, gen_key
from models.enums import HttpMethod

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
    id = db.Column(db.String(ACTION_ID_LENGTH), primary_key=True)
    path = db.Column(db.String(255), nullable=False)
    method = db.Column(db.String(15), nullable=False)
    description = db.Column(db.Text, default="", nullable=False)

    # ---- Init ----
    def __init__(self, path:str, method:str):
        if not path or not method:
            raise ValueError("Actions require a valid path and method.")
        
        if method not in HttpMethod._value2member_map_:
            raise ValueError(f"Invalid HTTP method '{method}'")
        self.description = f"Method {method} for path {path}."
        self.path = path
        self.method = method
        self.id = gen_key(path, method)

    # ---- Serialization ----
    def to_dict(self, *, include_roles: bool = True) -> dict:
        data = {
            "id": self.id,
            "description": self.description,
            "method": self.method,
            "path": self.path
        }
        if include_roles:
            data["roles"] = [r.id for r in (self.roles or [])]
        return data

    # ---- Queries (global session) ----

    @classmethod
    def by_path_and_method(cls, path: str, method:str) -> Optional["Action"]:        
        key = gen_key(path, method)
        return cls.by_id(key)

    @classmethod
    def get_id_length(cls):
        return cls.ACTION_ID_LENGTH

    @classmethod
    def by_id(cls, id: str):
        if len(id) != cls.get_id_length():
            return None
        return super().by_id(id)