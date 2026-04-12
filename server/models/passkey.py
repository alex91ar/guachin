# models/passkey.py
from __future__ import annotations

import base64
from typing import Optional

from sqlalchemy import Integer, String, LargeBinary, ForeignKey, select
from sqlalchemy.orm import Mapped, mapped_column, Session

from models.basemodel import Base
from models.db import get_session

class PassKey(Base):
    __tablename__ = "passkeys"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    credential_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    public_key: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    sign_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    credential_data: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)

    @staticmethod
    def by_credential_id(
        user_id: str,
        credential_id: str,
        session: Session | None = None,
    ) -> Optional["PassKey"]:
        owns_session = session is None
        session = session or get_session()
        try:
            stmt = select(PassKey).where(
                PassKey.user_id == user_id,
                PassKey.credential_id == credential_id,
            )
            return session.scalar(stmt)
        finally:
            if owns_session:
                session.close()


    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "credential_id": self.credential_id,
            "public_key_b64": base64.b64encode(self.public_key).decode("ascii"),
            "sign_count": self.sign_count,
        }