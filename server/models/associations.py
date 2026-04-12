# models/associations.py
from __future__ import annotations

from sqlalchemy import Table, Column, String, ForeignKey
from sqlalchemy.orm import relationship

from models.basemodel import Base


# ---------------------------
# Association tables
# ---------------------------

ROLE_ID_LEN = 255
USER_ID_LEN = 255
ACTION_ID_LEN = 16  # matches Action.ACTION_ID_LENGTH

# action <-> role (many-to-many)
role_actions = Table(
    "role_actions",
    Base.metadata,
    Column(
        "role_id",
        String(ROLE_ID_LEN),
        ForeignKey("roles.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "action_id",
        String(ACTION_ID_LEN),
        ForeignKey("actions.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)

# role <-> user (many-to-many)
user_roles = Table(
    "user_roles",
    Base.metadata,
    Column(
        "user_id",
        String(USER_ID_LEN),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "role_id",
        String(ROLE_ID_LEN),
        ForeignKey("roles.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


def wire_relationships():
    from models.action import Action
    from models.role import Role
    from models.user import User
    from models.user_session import UserSession
    from models.log import Log
    from models.passkey import PassKey
    from models.agent import Agent
    from models.syscall import Syscall


    # -------- Action <-> Role (many-to-many) --------
    Action.roles = relationship(
        "Role",
        secondary=role_actions,
        back_populates="actions",
        lazy="raise_on_sql",
    )
    Role.actions = relationship(
        "Action",
        secondary=role_actions,
        back_populates="roles",
        lazy="raise_on_sql",
    )

    # -------- Role <-> User (many-to-many) --------
    Role.users = relationship(
        "User",
        secondary=user_roles,
        back_populates="roles",
        lazy="raise_on_sql",
    )
    User.roles = relationship(
        "Role",
        secondary=user_roles,
        back_populates="users",
        lazy="raise_on_sql",
    )

    # -------- UserSession -> User (many-to-one) --------
    UserSession.user = relationship(
        "User",
        back_populates="sessions",
        lazy="raise_on_sql",
    )
    User.sessions = relationship(
        "UserSession",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="raise_on_sql",
    )

    # -------- Log -> User (many-to-one) --------
    Log.user = relationship(
        "User",
        back_populates="logs",
        lazy="raise_on_sql",
    )
    User.logs = relationship(
        "Log",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="raise_on_sql",
    )

    # -------- PassKey -> User (many-to-one) --------
    User.passkeys = relationship(
        "PassKey",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="raise_on_sql",
    )
    PassKey.user = relationship(
        "User",
        back_populates="passkeys",
        lazy="raise_on_sql",
    )

    # -------- Agent -> User (many-to-one) --------
    User.agents = relationship(
        "Agent",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="raise_on_sql",
    )
    Agent.user = relationship(
        "User",
        back_populates="agents",
        lazy="raise_on_sql",
    )

    # -------- Syscall -> Agent (many-to-one) --------
    Agent.syscalls = relationship(
        "Syscall",
        back_populates="agent",
        cascade="all, delete-orphan",
        lazy="raise_on_sql",
    )
    Syscall.agent = relationship(
        "Agent",
        back_populates="syscalls",
        lazy="raise_on_sql",
    )
