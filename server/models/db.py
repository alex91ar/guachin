# models/db.py
from __future__ import annotations
import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session, Session
from sqlalchemy.engine import Engine

engine: Engine | None = None
SessionLocal: scoped_session | None = None

logger = logging.getLogger(__name__)

def init_engine(database_url: str, *, echo: bool = False) -> None:
    global engine, SessionLocal
    if engine:
        logger.warning("SQLAlchemy engine already initialized; reusing existing connection.")
        return

    connect_args = {}

    # MySQL-specific connection tuning
    # Works for both pymysql and mysqlconnector drivers.
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
        future=True,
        pool_pre_ping=True,
        pool_size=20,          # default ~5
        max_overflow=40,       # extra connections beyond pool_size
        pool_timeout=30,       # seconds to wait before giving up
        pool_recycle=1800,     # recycle connections after N seconds
        pool_reset_on_return="rollback",
        connect_args=connect_args,
    )

    SessionLocal = scoped_session(
        sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    )
    logger.info("✅ SQLAlchemy engine initialized.")

def init_db(drop_all: bool = False) -> None:
    from models.basemodel import Base
    if not engine:
        raise RuntimeError("Engine not initialized. Call init_engine() first.")

    if drop_all:
        Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    logger.info("✅ Database tables initialized.")

def get_session() -> Session:
    """Return the scoped session proxy for this thread/request."""
    if SessionLocal is None:
        raise RuntimeError("SessionLocal not initialized. Call init_engine() first.")
    return SessionLocal  # NOTE: return proxy, not SessionLocal()
