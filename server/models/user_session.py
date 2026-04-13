# models/user_session.py
from __future__ import annotations

import base64
import json
import logging
import secrets
from datetime import datetime, timezone, timedelta
from typing import Optional
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from models.db import get_session
from models.user import User
from models.role import Role
import ipaddress
from flask import current_app, request, url_for
from flask_jwt_extended import create_access_token, create_refresh_token
from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, select
from sqlalchemy.orm import Mapped, Session, mapped_column
from user_agents import parse
from models.db import get_session
from models.action import Action
from models.basemodel import Base

logger = logging.getLogger(__name__)


def get_vals_from_token_unchecked(json_token: str):
    if not isinstance(json_token, str):
        raise ValueError("Value should be a string.")

    parts = json_token.split(".")
    if len(parts) != 3:
        raise ValueError("Invalid JWT.")

    try:
        middle = parts[1].strip()
        middle += "=" * (-len(middle) % 4)
        payload = json.loads(base64.b64decode(middle))
        return payload.get("exp", None), payload.get("iat", None), payload.get("sub", None)
    except Exception as e:
        logger.exception("Exception getting username from unchecked jwt: %s.", e)
        return None, None, None


def to_unix(dt: Optional[datetime]) -> int:
    if dt is None:
        return 0

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)

    return int(dt.timestamp())


def ua_string(ua_raw: str) -> str:
    ua = parse(ua_raw or "")
    browser = f"{ua.browser.family} {ua.browser.version_string}".strip()
    os_name = f"{ua.os.family} {ua.os.version_string}".strip()
    device = "Mobile" if ua.is_mobile else "Tablet" if ua.is_tablet else "Desktop"
    return f"{browser} on {os_name} ({device})"









class UserSession(Base):
    __tablename__ = "user_sessions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    access_token_sig: Mapped[Optional[str]] = mapped_column(String(127), nullable=True)
    sudo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    passkey: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    password: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    refresh_token_value: Mapped[Optional[str]] = mapped_column("refresh_token", String(1023), nullable=True)
    access_token_value: Mapped[Optional[str]] = mapped_column("access_token", Text, nullable=True)
    user_agent: Mapped[str] = mapped_column(Text, nullable=False)
    source_ip: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    created: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    valid_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    valid_until_refresh: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    partial: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_signup: Mapped[bool] = mapped_column(Boolean, nullable=False)

    user_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    @classmethod
    def by_id(
        cls,
        id: Any,
        session: Session | None = None,
        *,
        options: list | None = None,
    ):
        import inspect
        print(f"Loaded session {id} from {inspect.stack()[1].function} from {inspect.stack()[2].function}")
        ret = super().by_id(id, session=session, options=options)
        if ret is not None:
            print(f"Expiration = {ret.valid_until}")
        return ret

    def __init__(self, user_obj, is_signup=False):
        self.is_signup = is_signup
        self.id = secrets.token_hex(16)
        self.user = user_obj
        self.user_id = user_obj.id
        self.user_agent = ua_string(request.headers.get("User-Agent", ""))
        self.source_ip = request.remote_addr
        now = datetime.now(timezone.utc) - timedelta(seconds=1)
        self.created = now
        self.valid_until = now + current_app.config.get("JWT_ACCESS_TOKEN_EXPIRES")
        self.valid_until_refresh = now + current_app.config.get("JWT_REFRESH_TOKEN_EXPIRES")
        logger.info(f"Creating new session.")

    def refresh_tokens(self, session: Session = None) -> None:
        owns_session = session is None
        session = session or get_session()
        try:
            now = datetime.now(timezone.utc) - timedelta(seconds=1)

            obj = self
            if session is not None:
                existing = session.get(UserSession, self.id)
                if existing is not None and existing is not self:
                    obj = existing
                else:
                    obj = session.merge(self)

            obj.created = now
            obj.valid_until = now + current_app.config.get("JWT_ACCESS_TOKEN_EXPIRES")
            obj.valid_until_refresh = now + current_app.config.get("JWT_REFRESH_TOKEN_EXPIRES")

            session.commit()

            self.created = obj.created
            self.valid_until = obj.valid_until
            self.valid_until_refresh = obj.valid_until_refresh
        finally:
            if owns_session:
                session.close()

    @property
    def access_token(self) -> str:
        session = get_session()
        try:
            fresh = session.execute(
                select(UserSession)
                .options(
                    selectinload(UserSession.user)
                    .selectinload(User.roles)
                    .selectinload(Role.actions),
                    selectinload(UserSession.user)
                    .selectinload(User.passkeys),
                )
                .where(UserSession.id == self.id)
            ).unique().scalar_one()

            perms = set()
            print(f"sudo = {fresh.sudo}. password = {fresh.password}. passkey = {fresh.passkey}. is_signup = {fresh.is_signup}. partial = {fresh.partial}")
            if (fresh.sudo and fresh.password) or fresh.passkey or fresh.is_signup:
                for role_obj in fresh.user.roles:
                    for action in role_obj.actions:
                        perms.add(action.id)
                fresh.partial = False
            else:
                lookup_session = fresh._session_for_lookup()
                try:
                    twofa_action = Action.by_path_and_method(
                        lookup_session,
                        path=url_for("auth_api.me.login_twofa"),
                        method="POST",
                    )
                    passkey_action = Action.by_path_and_method(
                        lookup_session,
                        path=url_for("auth_api.passkeys.passkey_login_complete"),
                        method="POST",
                    )
                finally:
                    lookup_session.close()

                if twofa_action is not None:
                    perms.add(twofa_action.id)
                if passkey_action is not None:
                    perms.add(passkey_action.id)

                fresh.partial = True

            payload = {
                "sudo": fresh.sudo,
                "valid_password": fresh.password,
                "valid_passkey": fresh.passkey,
                "user_id": fresh.user_id,
                "perms": list(perms),
                "twofa_enabled": fresh.user.twofa_enabled,
                "environment": current_app.config.get("ENV"),
                "id": fresh.id,
                "exp": fresh.valid_until,
                "iat": fresh.created,
            }

            logger.info("Creating new access token sudo=%s.", fresh.sudo)
            token = create_access_token(identity=fresh.user_id, additional_claims=payload)
            fresh.access_token_value = token

            session.add(fresh)
            session.commit()

            self.access_token_value = fresh.access_token_value
            self.partial = fresh.partial
            return token

        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    @access_token.setter
    def access_token(self, access_token: str) -> None:
        session = get_session()
        exp, iat, user = get_vals_from_token_unchecked(access_token)
        self.access_token_value = access_token
        self.user_id = user
        self.valid_until = datetime.fromtimestamp(exp, tz=timezone.utc)
        self.created = datetime.fromtimestamp(iat, tz=timezone.utc)
        session.add(self)
        session.commit()
        session.close()

    @property
    def refresh_token(self) -> Optional[str]:
        session = get_session()
        try:
            fresh = session.execute(
                select(UserSession)
                .where(UserSession.id == self.id)
            ).unique().scalar_one()

            payload_refresh = {
                "user_id": fresh.user_id,
                "environment": current_app.config.get("ENV"),
                "id": fresh.id,
            }

            if fresh.valid_until_refresh:
                payload_refresh["exp"] = fresh.valid_until_refresh
                payload_refresh["iat"] = fresh.created

            token = create_refresh_token(identity=fresh.user_id, additional_claims=payload_refresh)
            fresh.refresh_token_value = token

            session.add(fresh)
            session.commit()

            self.refresh_token_value = fresh.refresh_token_value
            return token

        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    @refresh_token.setter
    def refresh_token(self, refresh_token: str) -> None:
        exp_r, _, _ = get_vals_from_token_unchecked(refresh_token)
        self.refresh_token_value = refresh_token
        self.valid_until_refresh = (
            datetime.fromtimestamp(exp_r, tz=timezone.utc) if exp_r is not None else None
        )
        self.save()

    def is_valid(self) -> bool:
        if self.valid_until is None:
            return False

        now = datetime.now(timezone.utc)
        vu = self.valid_until
        if vu.tzinfo is None:
            vu = vu.replace(tzinfo=timezone.utc)

        return vu > now

    def is_valid_refresh(self) -> bool:
        if self.valid_until_refresh is None:
            return False

        now = datetime.now(timezone.utc)
        vu = self.valid_until_refresh
        if vu.tzinfo is None:
            vu = vu.replace(tzinfo=timezone.utc)

        return vu > now

    def expire(self, session=None) -> None:
        if session is None:
            session = get_session()
        self.valid_until = None
        session.add(self)
        session.commit()
        session.close()
        

    def expire_refresh(self, session: Session = None) -> None:
        if session is None:
            session = get_session()
        self.valid_until_refresh = None
        session.add(self)
        session.commit()
        session.close()

    def to_dict(self) -> dict:
        return {
            "user_name": self.user_id,
            "id": self.id,
            "user_agent": self.user_agent,
            "source_ip": self.source_ip,
            "valid_until": to_unix(self.valid_until),
            "valid_until_refresh": to_unix(self.valid_until_refresh),
        }

    def is_elevated(self, user_obj) -> bool:
        auths = 0
        if self.sudo:
            return True
        if self.password:
            auths += 1
        if self.passkey:
            return True
        if not user_obj.can_2fa() and not user_obj.can_passkey():
            auths += 1
        return auths >= 2

    def get_jwts(self, session: Session = None):
        if session is None:
            owns_session = False
            session = get_session()
        else:
            owns_session = True
        try:
            fresh_self = session.execute(
                select(UserSession)
                .options(
                    selectinload(UserSession.user)
                    .selectinload(User.roles)
                    .selectinload(Role.actions)
                )
                .where(UserSession.id == self.id)
            ).unique().scalar_one()

            access = fresh_self.access_token
            refresh = fresh_self.refresh_token

            self.access_token_sig = fresh_self.access_token_sig
            self.valid_until = fresh_self.valid_until
            self.valid_until_refresh = fresh_self.valid_until_refresh
            self.created = fresh_self.created

            return access, refresh
        finally:
            if owns_session:
                session.close()

    def elevate(self, session: Session = None):
        owns_session = session is None
        if session is None:
            session = get_session()
        self.sudo = True
        session.merge(self)
        session.commit()
        if owns_session:
            session.close()
        return self.access_token, self.refresh_token


    @classmethod
    def delete_invalid_for_user(cls, session: Session, user_name: str) -> None:
        results = session.scalars(select(cls).where(cls.user_id == user_name)).all()
        for result in results:
            if not result.is_valid():
                session.delete(result)
        session.commit()


    @classmethod
    def clear_partial_sessions(cls, user_name: str, session=None) -> None:
        logger.info("Clearing partial sessions...")
        owns_session = session is None
        session = session or get_session()
        try:
            results = session.execute(
                select(cls).where(cls.user_id == user_name)
            ).unique().scalars().all()
            for result in results:
                if result.partial:
                    session.delete(result)

            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            if owns_session:
                session.close()

    @classmethod
    def by_refresh_token(cls, refresh_token: str, session =None):
        owns_session = session is None
        session = session or get_session()
        try:
            stmt = select(cls).where(cls.refresh_token_value == refresh_token)
            return list(session.scalars(stmt).all())
        finally:
            if owns_session:
                session.close()

    @classmethod
    def delete_by_jwt(cls, session: Session, jwt_value: str) -> bool:
        obj = cls.by_jwt(session, jwt_value)
        if obj:
            session.delete(obj)
            session.commit()
            return True
        return False

    @classmethod
    def by_jwt(cls, session: Session, jwt_value: str) -> Optional["UserSession"]:
        stmt = select(cls).where(cls.access_token_value == jwt_value).limit(1)
        return session.scalar(stmt)

    @classmethod
    def expire_sessions_by_role(cls, session: Session, role: str) -> int:
        from models.role import Role
        from models.user import User
        from utils import sanitize

        rid = sanitize(role).lower()
        now = datetime.now(timezone.utc)
        expired_count = 0

        user_ids_subq = select(User.id).where(User.roles.any(Role.id == rid))
        sessions_q = session.scalars(select(cls).where(cls.user_id.in_(user_ids_subq))).all()

        for sess in sessions_q:
            if sess.valid_until is not None:
                vu = sess.valid_until
                if vu.tzinfo is None:
                    vu = vu.replace(tzinfo=timezone.utc)
                if vu > now:
                    expired_count += 1
            sess.valid_until = None

        session.commit()
        logger.info("Expired %s session(s) for role '%s'.", expired_count, rid)
        return expired_count

    @staticmethod
    def _session_for_lookup() -> Session:
        from models.db import get_session

        return get_session()