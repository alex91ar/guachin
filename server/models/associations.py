# models/associations.py
from __future__ import annotations

from sqlalchemy.orm import relationship

from models.basemodel import Base, db


# ---------------------------
# Association db.Tables
# ---------------------------

ROLE_ID_LEN = 255
USER_ID_LEN = 255
ACTION_ID_LEN = 16  # matches Action.ACTION_ID_LENGTH

# action <-> role (many-to-many)
role_actions = db.Table(
    "role_actions",
    Base.metadata,
    db.Column(
        "role_id",
        db.String(ROLE_ID_LEN),
        db.ForeignKey("roles.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    db.Column(
        "action_id",
        db.String(ACTION_ID_LEN),
        db.ForeignKey("actions.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)

# role <-> user (many-to-many)
user_roles = db.Table(
    "user_roles",
    Base.metadata,
    db.Column(
        "user_id",
        db.String(USER_ID_LEN),
        db.ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    db.Column(
        "role_id",
        db.String(ROLE_ID_LEN),
        db.ForeignKey("roles.id", ondelete="CASCADE"),
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
    from models.line import Line
    from models.syscall import Syscall
    # -------- Action <-> Role (many-to-many) --------
    Action.roles = relationship(
        "Role",
        secondary=role_actions,
        back_populates="actions",
        lazy="selectin",
    )
    Role.actions = relationship(
        "Action",
        secondary=role_actions,
        back_populates="roles",
        lazy="selectin",
    )

    # -------- Role <-> User (many-to-many) --------
    Role.users = relationship(
        "User",
        secondary=user_roles,
        back_populates="roles",
        lazy="selectin",
    )
    User.roles = relationship(
        "Role",
        secondary=user_roles,
        back_populates="users",
        lazy="selectin",
    )

    # -------- UserSession -> User (many-to-one) --------
    UserSession.user = relationship(
        "User",
        back_populates="sessions",
        lazy="selectin",
    )
    User.sessions = relationship(
        "UserSession",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    # -------- Log -> User (many-to-one) --------
    Log.user = relationship(
        "User",
        back_populates="logs",
        lazy="selectin",
    )
    User.logs = relationship(
        "Log",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    # -------- PassKey -> User (many-to-one) --------
    User.passkeys = relationship(
        "PassKey",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    PassKey.user = relationship(
        "User",
        back_populates="passkeys",
    )


    # -------- Agent -> Line (one-to-many) --------
    Agent.lines = relationship(
        "Line",
        back_populates="agent",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="Line.timestamp",
    )
    Line.agent = relationship(
        "Agent",
        back_populates="lines",
        lazy="selectin",
    )


    User.agents = relationship(
    "Agent",
    back_populates="user",
    cascade="all, delete-orphan",
    lazy="selectin",
    )

    Agent.user = relationship(
        "User",
        back_populates="agents",
        lazy="selectin",
    )

    Agent.syscalls = relationship(
        "Syscall",
        back_populates="agent",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    Syscall.agent = relationship(
        "Agent",
        back_populates="syscalls",
        lazy="selectin",
    )
