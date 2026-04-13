from __future__ import annotations

import os
import logging
from pathlib import Path

from flask import Flask, Blueprint
from flask_wtf import CSRFProtect
from werkzeug.middleware.proxy_fix import ProxyFix

from routes import (
    request_validator,
    register_blueprints_from_package,
    enforce_rbac,
    sudo_validator,
    check_expired,
    session_loader,
    jwt,
)
import routes.auth, routes.anon, routes.html, routes.auth.sudo
from file_manager import init_admin
from utils import generate_urls
from models.db import init_engine, init_db
from config import ensure_min_entropy_keys
from fido2.server import Fido2Server
from fido2.webauthn import PublicKeyCredentialRpEntity


class IgnorePathFilter(logging.Filter):
    def __init__(self, blocked_paths):
        super().__init__()
        self.blocked_paths = set(blocked_paths)

    def filter(self, record):
        msg = record.getMessage()
        return not any(path in msg for path in self.blocked_paths)


csrf = CSRFProtect()


def _maybe_run_alembic(app: Flask):
    if os.environ.get("RUN_MIGRATIONS_ON_START") != "1":
        return

    alembic_ini = Path(__file__).with_name("alembic.ini")
    if not alembic_ini.exists():
        print("ℹ️ RUN_MIGRATIONS_ON_START=1 but alembic.ini not found; skipping migrations.")
        return

    try:
        from alembic import command
        from alembic.config import Config as AlembicConfig

        alembic_cfg = AlembicConfig(str(alembic_ini))
        alembic_cfg.set_main_option("sqlalchemy.url", app.config["DATABASE_URL"])
        command.upgrade(alembic_cfg, "head")
    except Exception as e:
        print(f"⚠️ Alembic migration failed or not installed: {e}")


def init_fido2(app: Flask):
    domain = app.config["DOMAIN"]
    rp = PublicKeyCredentialRpEntity(name=domain, id=domain)
    app.extensions["fido2_server"] = Fido2Server(rp)


def create_app():
    app = Flask(__name__)

    werkzeug_logger = logging.getLogger("werkzeug")
    werkzeug_logger.addFilter(IgnorePathFilter({
        "/api/v1/auth/agent/",
    }))

    anon_bp = Blueprint("anon_api", __name__, url_prefix="/api/v1/anon")
    auth_bp = Blueprint("auth_api", __name__, url_prefix="/api/v1/auth")
    sudo_bp = Blueprint("sudo_api", __name__, url_prefix="/api/v1/auth/sudo")
    html_bp = Blueprint("html_pages", __name__, url_prefix="/")

    env = os.environ.get("FLASK_ENV", "development")
    if env == "production":
        app.config.from_object("config.ProductionConfig")
        ensure_min_entropy_keys(app.config)
    else:
        logging.basicConfig(level=logging.INFO)
        app.config.from_object("config.DevelopmentConfig")
        ensure_min_entropy_keys(app.config, True)


    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL environment variable not set")

    app.config["DATABASE_URL"] = database_url

    init_engine(database_url)

    init_fido2(app)
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    _maybe_run_alembic(app)

    if app.config.get("ENV") == "development" and os.environ.get("INIT_DB_ON_START") == "1":
        print("🧱 INIT_DB_ON_START=1 — ensuring all tables exist via SQLAlchemy metadata...")
        init_db(drop_all=False)

    jwt.init_app(app)

    register_blueprints_from_package(
        app, routes.auth.sudo, sudo_bp,
        [request_validator, session_loader, enforce_rbac, sudo_validator, check_expired],
    )
    register_blueprints_from_package(
        app, routes.auth, auth_bp,
        [request_validator, session_loader, enforce_rbac, check_expired],
    )
    register_blueprints_from_package(
        app, routes.anon, anon_bp,
        [request_validator, session_loader],
    )
    register_blueprints_from_package(
        app, routes.html, html_bp,
        [request_validator, session_loader],
    )
    init_admin(app)
    csrf.init_app(app)
    csrf.exempt(html_bp)

    with app.app_context():
        generate_urls(app)

    @app.context_processor
    def inject_api_base_urls():
        return dict(api_base={
            "anon": "/api/v1/anon",
            "auth": "/api/v1/auth",
            "sudo": "/api/v1/auth/sudo",
            "html": "/",
        })

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5555)),
        debug=app.config.get("DEBUG", False),
        use_reloader=False,
    )