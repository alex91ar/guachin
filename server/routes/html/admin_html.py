from flask import Blueprint, render_template, send_from_directory, current_app
from models.user import User
from models.role import Role
from models.action import Action

bp = Blueprint("admin_html", "__name__", url_prefix="/admin_html")


@bp.route("/elevate")
def admin_elevate():
    return render_template("elevate.html")


@bp.route("/users")
def admin_users():
    return render_template("admin/dashboard.html", section="users")


@bp.route("/roles")
def admin_roles():
    return render_template("admin/dashboard.html", section="roles")


@bp.route("/actions")
def admin_actions():
    return render_template("admin/dashboard.html", section="actions")

@bp.route("/system")
def admin_system():
    return render_template("admin/dashboard.html", section="system")

@bp.route("/logs")
def admin_logs():
    return render_template("admin/dashboard.html", section="logs")

@bp.route("/configuration")
def admin_configuration():
    return render_template("admin/dashboard.html", section="configuration")

@bp.route("/admin/codicon.ttf", methods=["GET"])
def admin_codicon():
    return send_from_directory(current_app.static_folder+"/ttf", "codicon.ttf")

@bp.route("/", methods=["GET"])
def admin():
    return render_template("admin/dashboard.html")

