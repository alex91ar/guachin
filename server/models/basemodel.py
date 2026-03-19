# models/basemodel.py
from __future__ import annotations
import logging
from typing import Any, TypeVar, Type, List
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import select
from models.db import get_session

logger = logging.getLogger(__name__)

db = SQLAlchemy()

class Base(db.Model):
    """Base class for all ORM models."""
    __abstract__ = True

    def save(self) -> None:
        """Add and optionally commit the object."""
        db.session.add(self)
        db.session.commit()

    def delete(self) -> None:
        """Delete and optionally commit the object."""
        db.session.delete(self)
        db.session.commit()

    @classmethod
    def by_id(cls, id: str):
        return cls.query.get(id)

    @classmethod
    def by_id_lock(cls, id, session=None):
        session = session or get_session()
        stmt = select(cls).where(cls.id == id).with_for_update()
        return session.execute(stmt).scalar_one_or_none()

    @classmethod
    def all(cls):
        """Fetch all instances."""
        return cls.query.all()

    @classmethod
    def clear_table(cls, session=None) -> int:
        """
        Delete all rows from the table.

        Returns:
            int: number of rows deleted
        """
        session = session or db.session

        try:
            rows = session.query(cls).delete(synchronize_session=False)
            session.commit()
            logger.warning("Cleared table %s (%s rows deleted)", cls.__tablename__, rows)
            return rows
        except Exception:
            session.rollback()
            logger.exception("Failed to clear table %s", cls.__tablename__)
            raise
