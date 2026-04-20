# models/user.py
from __future__ import annotations

import base64
import io
import logging
from datetime import datetime
from typing import Optional, Tuple

import pyotp
import qrcode
from argon2 import PasswordHasher, exceptions as argon_errors
from flask import current_app
from flask_jwt_extended import get_jwt
from sqlalchemy import Boolean, DateTime, Integer, String, Text, select
from sqlalchemy.orm import Mapped, Session, mapped_column, selectinload

from models.basemodel import Base
from models.db import get_session
from utils import sanitize, normalize_email, check_password_complexity

logger = logging.getLogger(__name__)
ph = PasswordHasher()

legal_fields = [
    "legal_name",
    "legal_last_name",
    "legal_address",
    "legal_postal_code",
    "legal_phone_number",
    "legal_country_code",
]


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(256), primary_key=True)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    email: Mapped[Optional[str]] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    twofa_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    twofa_secret: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    fido2_state: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, default="")
    fido2_state_timestamp: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, default=None)
    credits: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    def __init__(
        self,
        id: str,
        *,
        email: str,
        description: str = "",
        twofa_enabled: bool = False,
        twofa_secret: str = "",
    ):
        self.id = sanitize(id).lower()
        self.description = description or ""
        self.email = normalize_email(email) if email else None
        self.twofa_enabled = bool(twofa_enabled)
        self.twofa_secret = twofa_secret or ""
        self.fido2_state = ""
        self.fido2_state_timestamp = None

    def can_passkey(self) -> bool:
        return self.is_loaded("passkeys") and len(self.passkeys) > 0

    def set_password(self, raw_password: str):
        ok, errors = check_password_complexity(raw_password)
        if not ok:
            return ok, errors
        self.password_hash = ph.hash(raw_password)
        return True, []

    def verify_password(self, raw_password: str) -> bool:
        try:
            return ph.verify(self.password_hash, raw_password)
        except argon_errors.VerifyMismatchError:
            return False

    def ensure_twofa_secret(self, session: Session | None = None) -> str:
        owns_session = session is None
        session = session or get_session()
        try:
            if not self.twofa_secret:
                self.twofa_secret = pyotp.random_base32()
                session.add(self)
                session.commit()
            return self.twofa_secret
        finally:
            if owns_session:
                session.close()

    def generate_2fa_qr(
        self,
        issuer: str = "guachin",
        session: Session | None = None,
    ) -> Tuple[str, str]:
        owns_session = session is None
        session = session or get_session()
        try:
            self.twofa_secret = ""
            secret = self.ensure_twofa_secret(session)
            uri = pyotp.totp.TOTP(secret).provisioning_uri(name=self.id, issuer_name=issuer)
            img = qrcode.make(uri)
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            return secret, f"data:image/png;base64,{base64.b64encode(buf.getvalue()).decode('ascii')}"
        finally:
            if owns_session:
                session.close()

    def can_2fa(self) -> bool:
        return self.twofa_enabled is True

    def verify_2fa(self, token: str) -> bool:
        totp = pyotp.TOTP(self.twofa_secret)
        if current_app.config.get("DEBUG", False):
            logger.info("Current totp: %s.", totp.now())
        try:
            return bool(totp.verify(token, valid_window=1))
        except Exception:
            return False

    def disable_2fa(
        self,
        token: str,
        force: bool = False,
        session: Session | None = None,
    ) -> bool:
        owns_session = session is None
        session = session or get_session()
        try:
            if not self.twofa_enabled or force:
                self.twofa_secret = ""
                self.twofa_enabled = False
                self.ensure_twofa_secret(session)
                session.add(self)
                session.commit()
                return True

            if self.verify_2fa(token):
                self.twofa_secret = ""
                self.twofa_enabled = False
                self.ensure_twofa_secret(session)
                session.add(self)
                session.commit()
                return True

            return False
        finally:
            if owns_session:
                session.close()

    def enable_2fa(self, token: str, session: Session | None = None) -> bool:
        owns_session = session is None
        session = session or get_session()
        try:
            if not self.verify_2fa(token):
                return False

            self.twofa_enabled = True
            session.add(self)
            session.commit()
            return True
        finally:
            if owns_session:
                session.close()

    def clear_roles(self, session: Session | None = None) -> None:
        owns_session = session is None
        session = session or get_session()
        try:
            self.roles = []
            session.add(self)
            session.commit()
        finally:
            if owns_session:
                session.close()

    def prune_sessions(self, session: Session | None = None) -> None:
        owns_session = session is None
        session = session or get_session()
        try:
            current_session_id = get_jwt().get("id")
            active_sessions = list(self.sessions) if self.is_loaded("sessions") else []

            for user_session in active_sessions:
                if user_session.id == current_session_id:
                    user_session.expire(session=session)
                else:
                    session.delete(user_session)

            session.commit()
        finally:
            if owns_session:
                session.close()

    def add_role(self, role_name: str, session: Session | None = None) -> None:
        from .role import Role

        owns_session = session is None
        session = session or get_session()
        try:
            rid = sanitize(role_name).lower()
            role = Role.by_id_with_actions(rid, session=session)
            if role is None:
                raise ValueError(f"Role '{rid}' not found")

            if role not in self.roles:
                self.roles.append(role)

            session.add(self)
            session.commit()
        finally:
            if owns_session:
                session.close()

    def delete_role(self, role_name: str, session: Session | None = None) -> None:
        from .role import Role

        owns_session = session is None
        session = session or get_session()
        try:
            rid = sanitize(role_name).lower()
            role = Role.by_id_with_actions(rid, session=session)

            if role and role in self.roles:
                self.roles.remove(role)
                session.add(self)
                session.commit()
        finally:
            if owns_session:
                session.close()

    def to_dict(self, *, include_roles: bool = True) -> dict:
        data = {
            "id": self.id,
            "description": self.description,
            "email": self.email,
            "twofa_enabled": self.twofa_enabled,
        }
        if include_roles and self.is_loaded("roles"):
            data["roles"] = [r.id for r in self.roles]
        return data

    def get_2fa_data(self, session: Session | None = None) -> dict:
        if not self.twofa_enabled:
            secret, qr = self.generate_2fa_qr(session=session)
            return {
                "twofa_qr": qr,
                "twofa_secret": secret,
                "twofa_enabled": False,
            }
        return {
            "twofa_enabled": True,
        }

    def to_dict_only_user(self) -> dict:
        return {
            "id": self.id,
            "twofa_enabled": self.twofa_enabled,
        }

    @classmethod
    def by_id(cls, id: str, session: Session | None = None) -> Optional["User"]:
        if session is None:
            session = get_session()
        from models.role import Role

        if not id or not id.isalnum():
            return None

        return super().by_id(
            sanitize(id).lower(),
            session=session,
            options=[
                selectinload(cls.roles).selectinload(Role.actions),
                selectinload(cls.sessions),
                selectinload(cls.passkeys),
            ],
        )

    @classmethod
    def by_email(cls, email: str, session: Session | None = None) -> Optional["User"]:
        from models.role import Role

        owns_session = session is None
        session = session or get_session()
        try:
            norm = normalize_email(email)
            stmt = (
                select(cls)
                .options(
                    selectinload(cls.roles).selectinload(Role.actions),
                    selectinload(cls.sessions),
                    selectinload(cls.passkeys),
                )
                .where(cls.email == norm)
                .limit(1)
            )
            return session.execute(stmt).unique().scalar_one_or_none()
        finally:
            if owns_session:
                session.close()