# models/syscall.py
from __future__ import annotations

import struct
from typing import Optional

from sqlalchemy import BigInteger, ForeignKey, Integer, String, UniqueConstraint, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from models.basemodel import Base
from models.db import get_session


class Syscall(Base):
    __tablename__ = "syscalls"
    __table_args__ = (
        UniqueConstraint("agent_id", "name", name="uq_syscalls_agent_name"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    agent_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[Optional[str]] = mapped_column(String(255))
    syscall: Mapped[Optional[int]] = mapped_column(BigInteger)

    def __init__(self, agent_id: str, name: str, syscall: int):
        self.agent_id = agent_id
        self.name = name
        self.syscall = syscall

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "agent_id": self.agent_id,
            "name": self.name,
            "syscall": self.syscall,
        }

    @classmethod
    def all_by_agent(
        cls,
        agent_id,
        session: Session | None = None,
        *,
        options: list | None = None,
    ):
        owns_session = session is None
        session = session or get_session()
        try:
            stmt = select(cls).where(cls.agent_id == agent_id)
            for opt in options or []:
                stmt = stmt.options(opt)
            return list(session.execute(stmt).unique().scalars().all())
        finally:
            if owns_session:
                session.commit()
                session.close()

    @classmethod
    def save_syscalls_bytes(cls, agent_id: str, data: bytes, session=None) -> None:
        print("Saving syscalls...")
        owns_session = session is None
        session = session or get_session()

        if not data:
            raise ValueError("Input string is empty")

        i = 0

        try:
            existing = set(
                session.execute(
                    select(cls.name).where(cls.agent_id == agent_id)
                ).scalars().all()
            )

            seen: set[str] = set()
            rows: list[dict] = []

            data_len = len(data)
            while i < data_len:
                name_len = data[i]
                start = i + 1
                end = start + name_len
                value_end = end + 8

                if value_end > data_len:
                    raise ValueError("Malformed syscall blob")

                name = data[start:end].decode("ascii")
                value = struct.unpack("<Q", data[end:value_end])[0]
                i = value_end

                if name in seen or name in existing:
                    continue

                seen.add(name)
                rows.append({
                    "agent_id": agent_id,
                    "name": name,
                    "syscall": value,
                })

            if not rows:
                print("No new syscalls to save.")
                return

            session.bulk_insert_mappings(cls, rows)
            session.commit()
            print(f"Successfully loaded {len(rows)} syscalls.")

        except Exception:
            print("Error saving syscalls")
            session.rollback()
            raise
        finally:
            if owns_session:
                session.close()

    @classmethod
    def sys(cls, agent_id: str, name: str) -> int:
        session = get_session()
        stmt = select(cls).where(
            cls.agent_id == agent_id,
            cls.name == name,
        ).limit(1)

        row = session.scalar(stmt)

        if row is None:
            raise LookupError(f"Syscall not found for agent_id={agent_id}, name={name}")

        return row.syscall