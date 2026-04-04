# app.py — SQLAlchemy / Alembic version (refactored for shared Base + init_engine)

from __future__ import annotations

import os
import logging
from pathlib import Path

from flask import Flask, Blueprint
from flask_wtf import CSRFProtect

from routes import (
    request_validator,
    register_blueprints_from_package,
    enforce_rbac,
    sudo_validator,
    check_expired,
    jwt,
)
import routes.auth, routes.anon, routes.html, routes.auth.sudo

# Database helpers
from utils import generate_urls
from models.db import init_engine, init_db, SessionLocal
from models.basemodel import db
from models.schema import populate_actions_from_routes, load_modules_from_directory
from config import ensure_min_entropy_keys
from werkzeug.middleware.proxy_fix import ProxyFix
from file_manager import init_admin
from fido2.server import Fido2Server
from fido2.webauthn import PublicKeyCredentialRpEntity

# --- Flask app and blueprints ---
app = Flask(__name__)

class IgnorePathFilter(logging.Filter):
    def __init__(self, blocked_paths):
        super().__init__()
        self.blocked_paths = set(blocked_paths)

    def filter(self, record):
        msg = record.getMessage()
        return not any(path in msg for path in self.blocked_paths)

werkzeug_logger = logging.getLogger("werkzeug")
werkzeug_logger.addFilter(IgnorePathFilter({
    "/api/v1/auth/agent/",
}))

anon_bp = Blueprint("anon_api", __name__, url_prefix="/api/v1/anon")
auth_bp = Blueprint("auth_api", __name__, url_prefix="/api/v1/auth")
sudo_bp = Blueprint("sudo_api", __name__, url_prefix="/api/v1/auth/sudo")
html_bp = Blueprint("html_pages", __name__, url_prefix="/")

csrf = CSRFProtect()


def _maybe_run_alembic(app: Flask):
    """
    Optionally run Alembic migrations on startup if:
      - RUN_MIGRATIONS_ON_START=1
      - alembic.ini exists
    """
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
        print("📜 Running Alembic migrations (upgrade head)...")
        command.upgrade(alembic_cfg, "head")
        print("✅ Alembic migrations complete.")
    except Exception as e:
        print(f"⚠️ Alembic migration failed or not installed: {e}")

def init_fido2(app):
    domain = app.config["DOMAIN"]
    rp = PublicKeyCredentialRpEntity(name=domain, id=domain)
    app.extensions["fido2_server"] = Fido2Server(rp)


def create_app(host=None):
    """
    Flask application factory.
    Configures environment, initializes DB, JWT, and registers routes.
    """
    # --- Configure environment ---
    env = os.environ.get("FLASK_ENV", "development")
    if env == "production":
        app.config.from_object("config.ProductionConfig")
        ensure_min_entropy_keys(app.config)
    else:
        logging.basicConfig(level=logging.INFO)
        app.config.from_object("config.DevelopmentConfig")
        ensure_min_entropy_keys(app.config, True)

    print(f"🌍 Running in {app.config['ENV']} mode")

    # --- Database initialization ---
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL environment variable not set")

    print(f"🗄️  Initializing SQLAlchemy engine for {database_url} ...")
    db.init_app(app)
    init_engine(database_url)
    init_fido2(app)
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    # Optional Alembic run
    _maybe_run_alembic(app)

    # Dev convenience: ensure tables exist if requested
    if app.config.get("ENV") == "development" and os.environ.get("INIT_DB_ON_START") == "1":
        print("🧱 INIT_DB_ON_START=1 — ensuring all tables exist via SQLAlchemy metadata...")
        init_db(drop_all=False)

    # --- Initialize JWT ---
    jwt.init_app(app)

    # --- Register blueprints ---
    register_blueprints_from_package(
        app, routes.auth.sudo, sudo_bp,
        [request_validator, enforce_rbac, sudo_validator, check_expired],
    )
    register_blueprints_from_package(
        app, routes.auth, auth_bp,
        [request_validator, enforce_rbac, check_expired],
    )
    register_blueprints_from_package(
        app, routes.anon, anon_bp,
        [request_validator],
    )
    register_blueprints_from_package(
        app, routes.html, html_bp,
        [request_validator],
    )

    csrf.init_app(app)
    csrf.exempt(html_bp)

    # --- Populate DB-driven schema data (routes, roles, etc.) ---
    with app.app_context():
        populate_actions_from_routes(app)
        load_modules_from_directory()
        generate_urls(app)
        init_admin(app)
    # --- Jinja globals for base URLs ---
    @app.context_processor
    def inject_api_base_urls():
        return dict(api_base={
            "anon": "/api/v1/anon",
            "auth": "/api/v1/auth",
            "sudo": "/api/v1/auth/sudo",
            "html": "/",
        })

    # --- Clean up SQLAlchemy scoped session ---
    @app.teardown_appcontext
    def shutdown_session(exc=None):
        if SessionLocal is not None:
            SessionLocal.remove()  # returns connection to pool, clears session

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5555)),
        debug=app.config.get("DEBUG", False),
        use_reloader=False
    )
