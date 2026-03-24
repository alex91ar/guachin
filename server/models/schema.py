# models/schema.py — SQLAlchemy/Postgres version (refactored for shared Base)

from __future__ import annotations

import logging
from typing import List

from flask import current_app, Flask
from sqlalchemy import select

from models.db import get_session, init_db
from models.action import Action
from models.role import Role
from models.user import User
from models.agent import Agent
from utils import gen_key, sanitize
from models.db import get_session
logger = logging.getLogger(__name__)


import glob
import os
import logging

from flask import jsonify
from utils import sanitize

logger = logging.getLogger(__name__)

from pathlib import Path
import glob
import os
import logging

from utils import sanitize
from models.basemodel import get_session

logger = logging.getLogger(__name__)
extra_paths = []



def get_action_keys() -> list[str]:
    """
    Retrieve all action keys (id values) from the actions table.
    Returns a list of string keys.
    """
    session = get_session()
    try:
        keys = [a.id for a in session.execute(select(Action)).scalars().all()]
        logger.info("Retrieved %d action keys", len(keys))
        logger.debug("Action keys: %s", keys)
        return keys
    except Exception:
        logger.exception("Failed to fetch action keys from 'actions'")
        return []


def populate_actions_from_routes(app: Flask, refresh: bool = False) -> bool:
    """
    Scans registered Flask routes and upserts Action rows for auth endpoints.
    - admin role gets ALL auth actions
    - user role gets only non-sudo auth actions
    """
    session = get_session()
    existing = set(get_action_keys())
    logger.info("Starting route scan to populate Action table")

    new_actions: List[str] = []
    new_non_sudo_actions: List[str] = []

    auth_prefix = "/api/v1/auth"
    sudo_prefix = f"{auth_prefix}/sudo/"

    try:
        for rule in app.url_map.iter_rules():
            path = str(rule.rule)
            if not path.startswith(auth_prefix):
                continue

            for method in rule.methods:
                if method in ["OPTIONS", "HEAD"]:
                    continue
                key = gen_key(path, method)
                is_sudo = path.startswith(sudo_prefix) or path.endswith("/get_sudo/")
                logger.debug("Created new rule %s with method %s. Key %s.", path, method, gen_key(path, method))
                if not is_sudo:
                    new_non_sudo_actions.append(key)
                new_actions.append(key)

                if key in existing and not refresh:
                    continue

                action = session.get(Action, key)
                if action is None:
                    action = Action(path=path, method=method)
                    session.add(action)
                else:
                    session.add(action)
        session.commit()

        # --- Ensure roles exist ---
        admin_role = session.get(Role, "administrator")
        if admin_role is None:
            admin_role = Role(id="administrator", description="Base administrator role")
            session.add(admin_role)

        user_role = session.get(Role, "user")
        if user_role is None:
            user_role = Role(id="user", description="Base user role")
            session.add(user_role)

        session.flush()

        # --- Clear and reassign actions ---
        admin_role.actions.clear()
        user_role.actions.clear()

        if new_actions:
            for k in set(new_actions):
                a = session.get(Action, k)
                if a:
                    admin_role.actions.append(a)
        if new_non_sudo_actions:
            for k in set(new_non_sudo_actions):
                a = session.get(Action, k)
                if a:
                    user_role.actions.append(a)

        session.commit()

        # --- Ensure admin user exists ---
        seed_admin_user(admin_role.id)

        logger.info(
            "Finished populating actions and roles: total=%d non_sudo=%d",
            len(new_actions),
            len(new_non_sudo_actions),
        )
        return True

    except Exception:
        session.rollback()
        logger.exception("populate_actions_from_routes failed")
        return False


def ensure_tables_exist() -> None:
    """
    Development helper: create SQL tables from metadata.
    In production, prefer Alembic migrations.
    """
    env = current_app.config.get("ENV") if current_app else "development"
    if env != "development":
        logger.info("Skipping table creation; ENV=%s (not development)", env)
        return

    try:
        init_db(drop_all=False)
        logger.info("SQL tables ensured (development mode).")
    except Exception:
        logger.exception("Failed to ensure SQL tables")





def seed_admin_user(admin_role_id: str) -> None:
    """
    Create a default admin user (id='admin', password=Admin123!) and ensure
    it has the admin role attached.
    """
    session = get_session()
    admin_user_id = "admin"
    admin_password = "Admin123!"
    admin_email = "test@test.com"

    try:
        role = session.get(Role, sanitize(admin_role_id).lower())
        if not role:
            role = Role(id="administrator", description="Base administrator role")
            session.add(role)
            session.flush()

        user = session.get(User, admin_user_id)
        if user is None:
            user = User(id=admin_user_id, description="Default admin", email=admin_email)
            user.set_password(admin_password)
            session.add(user)
            session.commit()
            logger.info("Created default admin user.")
        else:
            logger.info("Admin user already exists.")

        # Ensure admin role is attached
        if role not in user.roles:
            user.roles.append(role)
            session.add(user)
            session.commit()
            logger.info("Ensured admin role is attached to admin user.")

    except Exception:
        session.rollback()
        logger.exception("Failed to seed admin user")
