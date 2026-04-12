from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import delete, inspect, select
from sqlalchemy.orm import DeclarativeBase, Session

from models.db import get_session

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    __abstract__ = True

    def save(self, session: Session | None = None, *, commit: bool = True):
        owns_session = session is None
        session = session or get_session()
        try:
            if inspect(self).identity is None:
                print("New object using add.")
                session.add(self)
                obj = self
            else:
                print("Old object using merge.")
                obj = session.merge(self)

            if commit:
                session.commit()
                session.refresh(obj)

            for key, value in obj.__dict__.items():
                if not key.startswith("_sa_"):
                    setattr(self, key, value)

            return obj
        except Exception:
            session.rollback()
            raise
        finally:
            if owns_session:
                session.close()

    def delete(self, session: Session | None = None, *, commit: bool = True) -> None:
        owns_session = session is None
        session = session or get_session()
        try:
            session.delete(self)
            if commit:
                session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            if owns_session:
                session.close()

    @classmethod
    def by_id(
        cls,
        id: Any,
        session: Session | None = None,
        *,
        options: list | None = None,
    ):
        owns_session = session is None
        session = session or get_session()
        try:
            stmt = select(cls).where(cls.id == id)
            for opt in options or []:
                stmt = stmt.options(opt)
            return session.execute(stmt).unique().scalar_one_or_none()
        finally:
            if owns_session:
                session.close()

    @classmethod
    def all(
        cls,
        session: Session | None = None,
        *,
        options: list | None = None,
    ):
        owns_session = session is None
        session = session or get_session()
        try:
            stmt = select(cls)
            for opt in options or []:
                stmt = stmt.options(opt)
            return list(session.execute(stmt).unique().scalars().all())
        finally:
            if owns_session:
                session.close()

    @classmethod
    def all_by_user(
        cls,
        user_id,
        session: Session | None = None,
        *,
        options: list | None = None,
    ):
        owns_session = session is None
        session = session or get_session()
        try:
            stmt = select(cls).where(cls.user_id == user_id)
            for opt in options or []:
                stmt = stmt.options(opt)
            return list(session.execute(stmt).unique().scalars().all())
        finally:
            if owns_session:
                session.close()

    @classmethod
    def clear_table(cls, session: Session | None = None, *, commit: bool = True) -> int:
        owns_session = session is None
        session = session or get_session()
        try:
            result = session.execute(delete(cls))
            if commit:
                session.commit()
            rows = result.rowcount or 0
            logger.warning("Cleared table %s (%s rows deleted)", cls.__tablename__, rows)
            return rows
        except Exception:
            session.rollback()
            logger.exception("Failed to clear table %s", cls.__tablename__)
            raise
        finally:
            if owns_session:
                session.close()

    def is_loaded(self, attr: str) -> bool:
        return attr not in inspect(self).unloaded