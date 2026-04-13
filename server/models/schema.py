# models/schema.py

from __future__ import annotations

import importlib.util
import inspect
import logging
from pathlib import Path
from typing import List

from flask import Flask, current_app
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.orm import selectinload
from sqlalchemy.orm.attributes import set_committed_value

from models.action import Action
from models.db import get_session, init_db
from models.module import Module
from models.role import Role
from models.user import User
from utils import gen_key
import os

logger = logging.getLogger(__name__)

extra_paths: list[str] = []


def load_modules_from_directory(directory: str = "./modules", session: Session | None = None) -> None:
    module_dir = Path(directory)

    if not module_dir.exists() or not module_dir.is_dir():
        raise ValueError(f"Invalid module directory: {directory}")

    owns_session = session is None
    session = session or get_session()

    try:
        with session.no_autoflush:
            for file_path in module_dir.glob("*.py"):
                if file_path.name.startswith("__"):
                    continue

                module_name_for_import = f"dynamic_module_{file_path.stem}"
                spec = importlib.util.spec_from_file_location(
                    module_name_for_import,
                    str(file_path),
                )
                if spec is None or spec.loader is None:
                    logger.error("Could not load spec for %s", file_path)
                    continue

                py_module = importlib.util.module_from_spec(spec)
                try:
                    spec.loader.exec_module(py_module)
                except:
                    import traceback
                    logger.error(f"{file_path.name}: Could not load module.")
                    logger.exception(traceback.format_exc())
                    os.remove(file_path)
                    continue

                if not hasattr(py_module, "function"):
                    logger.error("%s missing 'function'", file_path.name)
                    os.remove(file_path)
                    continue

                func = getattr(py_module, "function")
                if not callable(func):
                    logger.error("'function' in %s is not callable", file_path.name)
                    os.remove(file_path)
                    continue
                sig = inspect.signature(func)
                if not all(name in sig.parameters for name in ["agent_id","args"]):
                    logger.error("'function' has not arguments \"agent_id\" and \"args\"", file_path.name)
                    os.remove(file_path)
                    continue


                name = getattr(py_module, "NAME", file_path.stem)
                params = getattr(py_module, "PARAMS", [])
                description = getattr(py_module, "DESCRIPTION", "")
                dependencies = getattr(py_module, "DEPENDENCIES", [])
                default = getattr(py_module, "DEFAULT", False)

                if not isinstance(params, list):
                    logger.error("%s: PARAMS must be a list", file_path.name)
                    os.remove(file_path)
                    continue

                code = ""
                for attr in dir(py_module):
                    value = getattr(py_module, attr)
                    if callable(value) and not attr.startswith("__"):
                        code += inspect.getsource(value)

                existing = Module.by_id(name, session=session)

                if existing:
                    existing.code = code
                    existing.params = params
                    existing.description = description
                    existing.dependencies = dependencies
                else:
                    session.add(
                        Module(
                            id=name,
                            code=code,
                            params=params,
                            description=description,
                            dependencies=dependencies,
                            default=default
                        )
                    )

        session.commit()
    except Exception:
        session.rollback()
        logger.exception("load_modules_from_directory failed")
        raise
    finally:
        if owns_session:
            session.close()


def get_action_keys(session: Session | None = None) -> list[str]:
    owns_session = session is None
    session = session or get_session()

    try:
        keys = list(session.scalars(select(Action.id)).all())
        logger.debug("Action keys: %s", keys)
        return keys
    except Exception:
        logger.exception("Failed to fetch action keys from 'actions'")
        return []
    finally:
        if owns_session:
            session.close()


def populate_actions_from_routes(
    app: Flask,
    refresh: bool = False,
    session: Session | None = None,
) -> bool:
    owns_session = session is None
    session = session or get_session()

    auth_prefix = "/api/v1/auth"
    sudo_prefix = f"{auth_prefix}/sudo/"

    new_actions: List[str] = []
    new_non_sudo_actions: List[str] = []

    try:
        existing = set(get_action_keys(session=session))

        for rule in app.url_map.iter_rules():
            path = str(rule.rule)
            if not path.startswith(auth_prefix) and not path.startswith("/admin/files"):
                continue

            if path.endswith(">"):
                path = path.rsplit("/", 1)[0] + "/"

            for method in rule.methods:
                if method in {"OPTIONS", "HEAD"}:
                    continue

                key = gen_key(path, method)
                is_sudo = path.startswith(sudo_prefix) or path.endswith("/get_sudo/")
                if key in existing:
                    continue
                logger.debug(
                    "Created new rule %s with method %s. Key %s.",
                    path,
                    method,
                    key,
                )

                new_actions.append(key)
                if not is_sudo:
                    new_non_sudo_actions.append(key)

                action = session.get(Action, key)

                if action is None:
                    action = Action(path=path, method=method)
                    session.add(action)
                elif refresh:
                    action.path = path
                    action.method = method

                existing.add(key)

        session.flush()

        admin_role = session.execute(
            select(Role)
            .options(selectinload(Role.actions))
            .where(Role.id == "administrator")
        ).unique().scalar_one_or_none()

        if admin_role is None:
            admin_role = Role(id="administrator", description="Base administrator role")
            session.add(admin_role)
            session.flush()
            set_committed_value(admin_role, "actions", [])

        user_role = session.execute(
            select(Role)
            .options(selectinload(Role.actions))
            .where(Role.id == "user")
        ).unique().scalar_one_or_none()

        if user_role is None:
            user_role = Role(id="user", description="Base user role")
            session.add(user_role)
            session.flush()
            set_committed_value(user_role, "actions", [])

        admin_actions = []
        for key in set(new_actions):
            action = session.get(Action, key)
            if action is not None:
                admin_actions.append(action)

        user_actions = []
        for key in set(new_non_sudo_actions):
            action = session.get(Action, key)
            if action is not None:
                user_actions.append(action)

        set_committed_value(admin_role, "actions", [])
        set_committed_value(user_role, "actions", [])

        admin_role.actions.extend(admin_actions)
        user_role.actions.extend(user_actions)

        seed_admin_user(admin_role.id, session=session)

        session.commit()

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
    finally:
        if owns_session:
            session.close()


def ensure_tables_exist() -> None:
    env = current_app.config.get("ENV") if current_app else "development"
    if env != "development":
        return

    try:
        init_db(drop_all=False)
    except Exception:
        logger.exception("Failed to ensure SQL tables")


from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.orm.attributes import set_committed_value

def seed_admin_user(admin_role_id: str, session: Session | None = None) -> None:
    owns_session = session is None
    session = session or get_session()

    admin_user_id = "admin"
    admin_password = "Admin123!"
    admin_email = "test@test.com"

    try:
        role = session.execute(
            select(Role)
            .options(selectinload(Role.actions))
            .where(Role.id == admin_role_id)
        ).unique().scalar_one_or_none()

        if role is None:
            role = Role(id="administrator", description="Base administrator role")
            session.add(role)
            session.flush()
            set_committed_value(role, "actions", [])

        user = session.execute(
            select(User)
            .options(selectinload(User.roles))
            .where(User.id == admin_user_id)
        ).unique().scalar_one_or_none()

        if user is None:
            user = User(id=admin_user_id, description="Default admin", email=admin_email)
            session.add(user)
            session.flush()
            set_committed_value(user, "roles", [])
            ok, errors = user.set_password(admin_password)
            if not ok:
                raise ValueError(f"Failed to set admin password: {errors}")

        if not user.is_loaded("roles"):
            set_committed_value(user, "roles", [])

        if role not in user.roles:
            user.roles.append(role)

        session.add(user)
        session.commit()
        logger.info("Ensured admin role is attached to admin user.")

    except Exception:
        session.rollback()
        logger.exception("Failed to seed admin user")
        raise
    finally:
        if owns_session:
            session.close()
            session.close()