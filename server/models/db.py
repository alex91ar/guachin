# models/db.py
from __future__ import annotations

import logging
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, scoped_session, sessionmaker

logger = logging.getLogger(__name__)

engine: Engine | None = None
SessionLocal: scoped_session[Session] | None = None


def init_engine(database_url: str, *, echo: bool = False) -> None:
    global engine, SessionLocal

    if engine is not None:
        logger.warning("SQLAlchemy engine already initialized; reusing existing connection.")
        return

    connect_args = {}

    if database_url.startswith("mysql"):
        connect_args.update({
            "charset": "utf8mb4",
            "connect_timeout": 10,
            "read_timeout": 30,
            "write_timeout": 30,
        })

    engine = create_engine(
        database_url,
        echo=echo,
        pool_pre_ping=True,
        pool_size=20,
        max_overflow=40,
        pool_timeout=30,
        pool_recycle=1800,
        pool_reset_on_return=None,
        connect_args=connect_args,
    )

    SessionLocal = scoped_session(
        sessionmaker(
            bind=engine,
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
            class_=Session,
        )
    )


def init_db(drop_all: bool = False) -> None:
    from models.basemodel import Base

    if engine is None:
        raise RuntimeError("Engine not initialized. Call init_engine() first.")

    if drop_all:
        Base.metadata.drop_all(bind=engine)

    Base.metadata.create_all(bind=engine)


def get_session() -> Session:
    if SessionLocal is None:
        raise RuntimeError("SessionLocal not initialized. Call init_engine() first.")
    return SessionLocal()


def remove_session() -> None:
    if SessionLocal is None:
        return
    SessionLocal.remove()


def get_db() -> Generator[Session, None, None]:
    db = get_session()
    try:
        yield db
    finally:
        remove_session()