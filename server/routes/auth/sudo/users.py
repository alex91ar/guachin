from flask import Blueprint, jsonify, request

from models.user import User
from models.user_session import UserSession
from utils import check_password_complexity
from sqlalchemy.orm import selectinload

bp = Blueprint("users", __name__, url_prefix="/users")


@bp.route("/", methods=["POST"])
def create_user():
    data = request.get_json() or {}
    user_id = data.get("id")
    email = data.get("email")
    password = data.get("password")
    roles = data.get("roles", [])

    if not all([user_id, email, password]):
        return jsonify({
            "result": "error",
            "message": "Missing required fields: id, email, password",
        }), 400

    if not isinstance(user_id, str) or not isinstance(email, str) or not isinstance(password, str):
        return jsonify({
            "result": "error",
            "message": "All fields must be strings",
        }), 422

    ok, errors = check_password_complexity(password)
    if not ok:
        return jsonify({
            "result": "error",
            "message": "Password not complex enough:\n" + "\n".join(errors),
        }), 400

    new_user = User.by_id(user_id)
    if new_user:
        return jsonify({
            "result": "error",
            "message": f"Username '{user_id}' already exists",
        }), 409

    new_user = User.by_email(email)
    if new_user:
        return jsonify({
            "result": "error",
            "message": f"A user with email '{email}' already exists",
        }), 409

    new_user = User(id=user_id, email=email)
    ok, pw_errors = new_user.set_password(password)
    if not ok:
        return jsonify({
            "result": "error",
            "message": "Password not complex enough:\n" + "\n".join(pw_errors),
        }), 400

    if roles and isinstance(roles, list):
        for role_name in roles:
            new_user.add_role(role_name)

    new_user.save()

    return jsonify({
        "result": "success",
        "message": new_user.to_dict(),
    }), 201


@bp.route("/", methods=["GET"])
def list_users():
    users = User.all(options=[
                selectinload(User.roles),
            ])
    return jsonify({
        "result": "success",
        "message": [u.to_dict() for u in users],
    }), 200


@bp.route("/", methods=["PUT"])
def update_user():
    data = request.get_json() or {}
    username = data.get("id", "")

    user = User.by_id(username)
    if not user:
        return jsonify({"result": "error", "message": "User not found"}), 404

    if "email" in data:
        user.email = data["email"]

    if "password" in data:
        ok, errors = user.set_password(data["password"])
        if not ok:
            return jsonify({
                "result": "error",
                "message": "Password not complex enough:\n" + "\n".join(errors),
            }), 400

    if "roles" in data and isinstance(data["roles"], list):
        user.clear_roles()
        for role in data["roles"]:
            user.add_role(role)

    user.prune_sessions()

    return jsonify({"result": "success", "message": user.to_dict()}), 200


def change_password(user_obj, new_pw):
    ok, errors = user_obj.set_password(new_pw)
    if not ok:
        return jsonify({
            "result": "error",
            "message": "Password not complex enough:\n" + "\n".join(errors),
        }), 400

    user_obj.prune_sessions()
    return jsonify({"result": "ok", "message": "Password updated"})


@bp.route("/action", methods=["PUT"])
def do_user_action():
    data = request.get_json() or {}

    username = data.get("id", "")
    action = data.get("action", "")
    value = data.get("value", "")

    if not isinstance(username, str) or not isinstance(action, str):
        return jsonify({"result": "error", "message": "Invalid Input"}), 400

    user_obj = User.by_id(username)
    if not user_obj:
        return jsonify({"result": "error", "message": "User not found"}), 404

    if action == "disable_twofa":
        return disable_user_2fa(user_obj)
    elif action == "delete":
        return delete_user(user_obj)
    elif action == "expire":
        return expire_user(value)
    elif action == "change_password":
        if not isinstance(value, str):
            return jsonify({"result": "error", "message": "Invalid Input"}), 400
        return change_password(user_obj, value)
    else:
        return jsonify({"result": "error", "message": "Invalid action"}), 400


def disable_user_2fa(user_obj):
    if not user_obj.twofa_enabled:
        return jsonify({
            "result": "error",
            "message": f"{user_obj.id} doesn't have 2fa enabled.",
        }), 422

    user_obj.disable_2fa(token="", force=True)
    return jsonify({
        "result": "success",
        "message": f"Disabled 2fa for user {user_obj.id}.",
    }), 202


def delete_user(user_obj):
    user_obj.delete()
    return jsonify({
        "result": "success",
        "message": f"User '{user_obj.id}' deleted successfully",
    }), 202


def expire_user(short_session_id):
    token_obj = UserSession.by_id(short_session_id)
    if token_obj is None:
        return jsonify({"result": "error", "message": "Session not found"}), 404

    token_obj.valid_until = None

    return jsonify({
        "result": "success",
        "message": f"Session '{short_session_id}' expired.",
    }), 202