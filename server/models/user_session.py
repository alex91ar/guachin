# models/action.py
from __future__ import annotations

from typing import Optional
import logging
import secrets
from sqlalchemy import (
    String, ForeignKey, select, Boolean, Text, DateTime
)
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime, timezone
from models.basemodel import Base, db
from models.db import get_session
from models.action import Action
import json
import base64
import uuid
from user_agents import parse
from flask import request, url_for, current_app
from flask_jwt_extended import create_access_token,create_refresh_token, jwt_required, get_jwt_identity, get_jwt
import ipaddress
import geoip2.database

logger = logging.getLogger(__name__)

def get_vals_from_token_unchecked(json_token):
    if not isinstance(json_token, str):
        raise ValueError("Value should be a string.")
    parts = json_token.split(".")
    if len(parts) != 3:
        raise ValueError("Invalid JWT.")
    try:
        middle = parts[1].strip()
        middle += "=" * (4 - (len(middle) % 4))
        payload = json.loads(base64.b64decode(middle))
        return payload.get("exp",None), payload.get("iat",None), payload.get("sub",None)
    except Exception as e:
        logger.exception("Exception getting username from unchecked jwt: %s.", e)
        return None, None, None

def to_unix(dt):
    if dt is None:
        return 0

    # ensure timezone-aware
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)

    return int(dt.timestamp())

def ua_string(ua_raw: str) -> str:
    ua = parse(ua_raw or "")
    browser = f"{ua.browser.family} {ua.browser.version_string}".strip()
    os = f"{ua.os.family} {ua.os.version_string}".strip()
    device = "Mobile" if ua.is_mobile else "Tablet" if ua.is_tablet else "Desktop"

    return f"{browser} on {os} ({device})"

GEO_READER = geoip2.database.Reader("./GeoLite2-City.mmdb")


def lan_or_class_label(ip: str) -> str | None:
    """
    Returns a LAN/Class label if the IP is localhost, private LAN, multicast,
    reserved, or link-local. Otherwise returns None (meaning: go geo).
    """
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return "Unknown"

    # 1) Localhost
    if addr.is_loopback:
        return "Localhost"

    # 2) LAN / private ranges
    if addr.is_private:
        # RFC1918 private ranges map to classic classes:
        if addr in ipaddress.ip_network("10.0.0.0/8"):
            return "LAN Class A"
        if addr in ipaddress.ip_network("172.16.0.0/12"):
            return "LAN Class B"
        if addr in ipaddress.ip_network("192.168.0.0/16"):
            return "LAN Class C"
        # other private (rare) still LAN
        return "LAN (Private)"

    # Link-local (like 169.254.x.x)
    if addr.is_link_local:
        return "LAN (Link-local)"

    # Multicast / reserved / unspecified / etc.
    if addr.is_multicast:
        return "Class D (Multicast)"
    if addr.is_reserved or addr.is_unspecified:
        return "Class E (Reserved)"

    # Not local -> go geo
    return None


def geo_string(ip: str) -> str:
    """
    Returns a single geo string "City, Region, Country" or "Unknown".
    """
    try:
        r = GEO_READER.city(ip)
        city = r.city.name
        region = r.subdivisions.most_specific.name
        country = r.country.name or r.country.iso_code

        parts = [p for p in (city, region, country) if p]
        return ", ".join(parts) if parts else "Unknown"
    except Exception:
        return "Unknown"


def ip_label(ip: str) -> str:
    """
    Full ordered logic:
    Localhost -> LAN/Class -> Geo
    Always returns a single string.
    """
    label = lan_or_class_label(ip)
    if label is not None:
        return label
    return geo_string(ip)


class UserSession(Base):
    """
    User Session tokens.
    - Primary key: json_token
    - Many-to-many with User via role_actions
    """
    __tablename__ = "user_sessions"

    # Token itself is PK
    id = db.Column(db.String(32), primary_key=True)
    access_token_sig = db.Column(db.String(127), nullable=True)
    sudo = db.Column(db.Boolean, nullable=False, default=False)
    passkey = db.Column(db.Boolean, nullable=False, default=False)
    password = db.Column(db.Boolean, nullable=False, default=False)
    refresh_token = db.Column(db.String(1023), nullable=False)
    access_token = db.Column(db.Text, nullable=False)
    user_agent = db.Column(db.Text, nullable=False)
    geo_location = db.Column(db.String(128), nullable=True)
    source_ip = db.Column(db.String(45), nullable=True)
    created = db.Column(db.DateTime(timezone=True), nullable=True)
    valid_until = db.Column(db.DateTime(timezone=True), nullable=True)
    valid_until_refresh = db.Column(db.DateTime(timezone=True), nullable=True)
    partial = db.Column(db.Boolean, nullable=False, default=True)

    user_id = db.Column(
        db.String(255),
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # ---- Init ----
    def __init__(self, user_obj):
        self.id = secrets.token_hex(16)
        self.user_id = user_obj.id
        self.user = user_obj
        self.user_agent = ua_string(request.headers.get("User-Agent",""))
        self.geo_location = ip_label(request.remote_addr)
        self.source_ip = request.remote_addr
        logger.info("Creating new session.")

    def refresh_tokens(self):
        self.valid_until = datetime.now() + current_app.config.get("JWT_ACCESS_TOKEN_EXPIRES")
        self.valid_until_refresh = datetime.now() + current_app.config.get("JWT_REFRESH_TOKEN_EXPIRES")
        self.save()

    @property
    def access_token(self):
        perms = set()
        if (self.sudo and self.password) or self.passkey:
            for role_obj in self.user.roles:
                for action in role_obj.actions:
                    perms.add(action.id)
            self.partial = False
        else:
            twofa_action = Action.by_path_and_method(path=url_for('auth_api.me.login_twofa'), method='POST')
            passkey_action = Action.by_path_and_method(path=url_for('auth_api.passkeys.passkey_login_complete'), method='POST')
            perms.add(twofa_action.id)
            perms.add(passkey_action.id)
            self.partial = True
        payload = {
            "sudo":            self.sudo,
            "valid_password":   self.password,
            "valid_passkey":    self.passkey,
            "user_id":        self.user.id,
            "perms":     list(perms),
            "twofa_enabled":   self.user.twofa_enabled,
            "environment": current_app.config.get("ENV"),
            "id":self.id
        }
        if self.valid_until:
            payload["exp"] = self.valid_until
            payload["iat"] = self.created
        ua = request.headers.get("User-Agent","")
        logger.info(f"Creating new access token sudo={self.sudo}.")
        token = create_access_token(identity=self.user.id, additional_claims=payload)
        self.access_token = token
        return token

    @access_token.setter
    def access_token(self, access_token: str) -> None:
        exp, iat, user = get_vals_from_token_unchecked(access_token)
        self.user_id = user
        self.valid_until = datetime.fromtimestamp(exp, tz=timezone.utc)
        self.created = datetime.fromtimestamp(iat, tz=timezone.utc)
        self.save()

    @property
    def refresh_token(self) -> Optional[str]:
        payload_refresh = {
            "user_id": self.user.id,
            "environment": current_app.config.get("ENV"),
            "id":self.id
        }
        if self.valid_until_refresh:
            payload_refresh["exp"] = self.valid_until_refresh
            payload_refresh["iat"] = self.created
        token = create_refresh_token(identity=self.user.id, additional_claims=payload_refresh)
        self.refresh_token = token
        return token

    @refresh_token.setter
    def refresh_token(self, refresh_token: str) -> None:
        exp_r, iat_r, user_r = get_vals_from_token_unchecked(refresh_token)
        self.valid_until_refresh =  datetime.fromtimestamp(exp_r, tz=timezone.utc)
        self.save()

    def is_valid(self) -> bool:
        """
        Return True if this session is still valid based on valid_until.
        """
        if self.valid_until is None:
            return False

        now = datetime.now(timezone.utc)

        vu = self.valid_until
        if vu.tzinfo is None:
            # normalize naive datetimes to UTC
            vu = vu.replace(tzinfo=timezone.utc)

        return vu > now

    def is_valid_refresh(self) -> bool:
        """
        Return True if this session is still valid based on valid_until.
        """
        if self.valid_until_refresh is None:
            return False

        now = datetime.now(timezone.utc)

        vu = self.valid_until_refresh
        if vu.tzinfo is None:
            # normalize naive datetimes to UTC
            vu = vu.replace(tzinfo=timezone.utc)

        return vu > now

    def expire(self):
        self.valid_until = None
        db.session.commit()
    
    def expire_refresh(self):
        self.valid_until_refresh = None
        db.session.commit()

    # ---- Serialization ----
    def to_dict(self) -> dict:
        data = {
            "user_name": self.user_id,
            "id":self.id,
            "user_agent":self.user_agent,
            "source_ip": self.source_ip,
            "valid_until": to_unix(self.valid_until),
            "valid_until_refresh": to_unix(self.valid_until_refresh),
            "geo_location":self.geo_location,
            "elevated":self.is_elevated()
        }
        return data

    def is_elevated(self) -> bool:
        auths = 0
        if self.sudo:
            auths +=auths+1
        if self.password:
            auths += auths+1
        if self.passkey:
            auths += auths+1
        if not self.user.can_2fa() and not self.user.can_passkey():
            auths +=1
        if auths >= 2:
            return True
        return False        

    def get_jwts(self):
        return self.access_token, self.refresh_token

    def elevate(self):
        self.sudo = True
        self.save()
        return self.access_token, self.refresh_token

    # ---- Queries (global session) ----
    @classmethod
    def by_user_name(cls, user_name: str):        
        return cls.query.filter_by(user_id=user_name)

    @classmethod
    def delete_invalid_for_user(cls, user_name: str):
        results = cls.query.filter_by(user_id=user_name)
        for result in results:
            if not result.is_valid():
                result.delete()
        db.session.commit()

    @classmethod
    def by_id(cls, id: str):
        return super().by_id(id)
        
    @classmethod
    def clear_partial_sessions(cls, user_name:str):
        logger.info("Clearing partial sessions...")
        results = cls.query.filter_by(user_id=user_name)
        for result in results:
            if result.partial:
                result.delete()
        db.session.commit()

    @classmethod
    def by_refresh_token(cls, refresh_token: str):
        return cls.query.filter_by(refresh_token = refresh_token)

    @classmethod
    def delete_by_jwt(cls, jwt):
        obj = cls.by_jwt(jwt)
        if obj:
            obj.delete()
            db.session.commit()
            return True
        return False
    

    @classmethod
    def expire_sessions_by_role(cls, role: str) -> int:
        """
        Expire all sessions belonging to users that have `role`.

        Role matching is done on Role.id (lowercased + sanitized),
        consistent with User.add_role/delete_role.

        Returns:
            int: number of sessions that were expired
        """
        from models.user import User
        from models.role import Role
        from utils import sanitize

        rid = sanitize(role).lower()
        session = get_session()
        now = datetime.now(timezone.utc)
        expired_count = 0

        with session.begin():
            # subquery of user IDs who have this role
            user_ids_subq = (
                select(User.id)
                .where(User.roles.any(Role.id == rid))
            )

            # sessions for those users
            sessions_q = session.query(cls).filter(
                cls.user_id.in_(user_ids_subq)
            )

            for sess in sessions_q.yield_per(500):
                # count only currently-valid sessions
                if sess.valid_until is not None:
                    vu = sess.valid_until
                    if vu.tzinfo is None:
                        vu = vu.replace(tzinfo=timezone.utc)
                    if vu > now:
                        expired_count += 1

                sess.valid_until = None  # expire

        logger.info("Expired %s session(s) for role '%s'.", expired_count, rid)
        return expired_count
