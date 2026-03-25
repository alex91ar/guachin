# models/basemodel.py
from __future__ import annotations
import logging
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import select
from models.db import get_session

logger = logging.getLogger(__name__)

db = SQLAlchemy()

class Base(db.Model):
    __abstract__ = True

    def save(self, session=None) -> None:
        session = session or db.session
        try:
            session.add(self)
            session.commit()
        except Exception:
            session.rollback()
            raise

    def delete(self, session=None) -> None:
        session = session or db.session
        try:
            session.delete(self)
            session.commit()
        except Exception:
            session.rollback()
            raise

    @classmethod
    def by_id(cls, id: str):
        return cls.query.get(id)

    @classmethod
    def by_id_lock(cls, id, session=None):
        session = session or get_session()
        stmt = select(cls).where(cls.id == id).with_for_update()
        return (session, session.execute(stmt).scalar_one_or_none())

    @classmethod
    def all(cls):
        return cls.query.all()

    @classmethod
    def clear_table(cls, session=None) -> int:
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