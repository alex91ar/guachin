from flask_jwt_extended import jwt_required, get_jwt, get_jwt_identity, JWTManager

# routes/html/html.py
from flask import Blueprint, render_template, current_app, send_from_directory, abort
from models.db import get_session


bp = Blueprint("html", __name__, url_prefix="/")

@bp.route("/")
def home():
    """Landing page"""
    return render_template("index.html", title="Home")

@bp.route("/profile", methods=["GET"])
def profile_page():
    return render_template("account/profile.html")

@bp.route("/security", methods=["GET"])
def security_page():
    return render_template("account/security.html")

@bp.route("/login", methods=["GET"])
def login_page():
    """Login page"""
    return render_template("account/login.html", title="Login")

@bp.route("/signup")
def signup_page():
    """Login page"""
    return render_template("account/signup.html", title="Signup")

@bp.route("/reset", methods=["GET"])
def reset_page():
    """
    Serves the password reset page (reset.html).
    """
    return render_template("account/reset.html", title="Reset")

@bp.route("/agents", methods=["GET"])
def agents_page():
    """
    Serves the agents page (agents.html).
    """
    return render_template("agents.html", title="Agents")

@bp.route("/codicon.ttf", methods=["GET"])
def codicon():
    return send_from_directory(current_app.static_folder+"/ttf", "codicon.ttf")

@bp.route("/file-manager-iframe", methods=["GET"])
def file_manager():
    return render_template("admin/file-manager.html")

@bp.route("/websocket", methods=["GET"])
def websocket():
    if current_app.config.get("DEBUG") == True:
        return render_template("websocket_test.html")
    else:
        abort(404)

@bp.route("/filemanager", methods=["GET"])
def filemanager():
    return render_template("file_manager.html")

@bp.route("/processmanager", methods=["GET"])
def processmanager():
    return render_template("process_manager.html")