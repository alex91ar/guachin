# models/user.py
from __future__ import annotations
from flask import current_app
from flask_jwt_extended import get_jwt
from typing import Optional, List, Iterable, Tuple
import base64
import io
import logging

import pyotp
import qrcode
from argon2 import PasswordHasher, exceptions as argon_errors

from sqlalchemy import (
    String, Text, Table, Column, ForeignKey, Boolean, Integer, select, and_
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.basemodel import Base, db
from utils import sanitize, normalize_email, check_password_complexity

logger = logging.getLogger(__name__)
ph = PasswordHasher()

legal_fields = ["legal_name","legal_last_name","legal_address","legal_postal_code","legal_phone_number","legal_country_code"]

class User(Base):
    """
    User model
    """
    __tablename__ = "users"

    # ---------- Core identifiers ----------
    id = db.Column(db.String(255), primary_key=True)
    description = db.Column(db.Text, default="", nullable=False)

    # ---------- Public columns ----------
    email = db.Column(db.String(255), unique=True, index=True)
    password_hash = db.Column(db.String(255), default="", nullable=False)

     # Auth / security
    twofa_enabled = db.Column(db.Boolean, default=False, nullable=False)
    twofa_secret = db.Column(db.String(64), default="", nullable=False)
    fido2_state  = db.Column(db.String(255), nullable=True, default="")
    fido2_state_timestamp  = db.Column(db.DateTime, nullable=True, default=None)
    credits = db.Column(db.Integer, nullable=False, default=0)
    # --------------- Init ---------------
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
        if len(self.passkeys) == 0:
            return False
        return True

    # --------------- Password helpers ---------------
    def set_password(self, raw_password: str):
        ok, error = check_password_complexity(raw_password)
        if not ok:
            return ok, error
        self.password_hash = ph.hash(raw_password)
        db.session.commit()
        return True, []

    def verify_password(self, raw_password: str) -> bool:
        try:
            return ph.verify(self.password_hash, raw_password)
        except argon_errors.VerifyMismatchError:
            return False

    # --------------- 2FA helpers ---------------
    def ensure_twofa_secret(self) -> str:
        if not self.twofa_secret:
            self.twofa_secret = pyotp.random_base32()
            db.session.commit()
        return self.twofa_secret

    def generate_2fa_qr(self, issuer: str = "guachin") -> Tuple[str, str]:
        """
        Returns (secret, data_uri_png)
        """
        self.twofa_secret = ""
        secret = self.ensure_twofa_secret()
        uri = pyotp.totp.TOTP(secret).provisioning_uri(name=self.id, issuer_name=issuer)
        img = qrcode.make(uri)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode("ascii")
        return secret, f"data:image/png;base64,{b64}"

    def can_2fa(self) -> bool:
        if self.twofa_enabled == False:
            return False

    def verify_2fa(self, token: str) -> bool:
        totp = pyotp.TOTP(self.twofa_secret)
        if current_app.config.get("DEBUG", False):
            logger.info("Current totp: %s.", totp.now())
        try:
            return bool(totp.verify(token, valid_window=1))
        except Exception:
            return False

    def disable_2fa(self, token, force=False):
        if not self.twofa_enabled or force:
            self.twofa_secret = ""
            self.ensure_twofa_secret()
            return True
        elif self.verify_2fa(token):
            self.twofa_secret = ""
            self.twofa_enabled = False
            self.ensure_twofa_secret()
            db.session.commit()
            return True
        return False

    def enable_2fa(self, token:str) -> bool:
        if not self.verify_2fa(token):
            return False
        self.twofa_enabled = True
        db.session.commit()
        self.prune_sessions()
        return True

    # --------------- Role helpers (use global session) ---------------
    def clear_roles(self) -> None:
        self.roles = []
        db.session.commit()
    
    def prune_sessions(self):
        id = get_jwt().get("id")
        sessions = self.sessions
        for i in range(len(sessions) - 1, -1, -1):
            if sessions[i].id == id:
                sessions[i].expire()
                continue
            sessions[i].delete()
    
    def add_role(self, role_name: str) -> None:
        from .role import Role
        rid = sanitize(role_name).lower()
        role = Role.by_id(rid)
        if role is None:
            raise ValueError(f"Role '{rid}' not found")
        if role not in self.roles:
            self.roles.append(role)
        db.session.commit()

    def delete_role(self, role_name: str) -> None:
        from .role import Role
        rid = sanitize(role_name).lower()
        role = Role.by_id(rid)
        if role and role in self.roles:
            self.roles.remove(role)
            db.session.commit()

    # --------------- Serialization ---------------
    def to_dict(self, *, include_roles: bool = True) -> dict:
        data = {
            "id": self.id,
            "description": self.description,
            "email": self.email,
            "twofa_enabled": self.twofa_enabled,
        }
        if include_roles:
            data["roles"] = [r.id for r in (self.roles or [])]
        return data

    def get_2fa_data(self) -> dict:
        if not self.twofa_enabled:
            secret, qr = self.generate_2fa_qr()
            data = {
                "twofa_qr":qr,
                "twofa_secret":secret,
                "twofa_enabled":False
            }
        else:
            data = {
                "twofa_enabled":True
            }
        return data

    def to_dict_only_user(self) -> dict:
        return {"id": self.id, "twofa_enabled": self.twofa_enabled}

    # --------------- Query helpers (global session) ---------------
    @classmethod
    def by_id(cls, id: str) -> Optional["User"]:
        if not id.isalnum():
            return None
        return super().by_id(sanitize(id).lower())

    @classmethod
    def by_email(cls, email: str) -> Optional["User"]:
        norm = normalize_email(email)
        return cls.query.filter_by(email = norm).first()


    