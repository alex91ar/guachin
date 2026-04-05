from flask import Blueprint, jsonify, request

from models.action import Action
from models.role import Role
from models.user_session import UserSession
from utils import sanitize

bp = Blueprint("roles", __name__, url_prefix="/roles")


def add_actions_to_role(role_name, actions):
    role = Role.by_id(sanitize(role_name))
    if not role:
        return jsonify({
            "result": "error",
            "message": "Role not found",
        }), 404

    action_list = []
    seen = set()

    for a in actions or []:
        action_id = a.get("id") if isinstance(a, dict) else a
        if not action_id:
            continue

        action_id = sanitize(action_id)
        if action_id in seen:
            continue

        action_obj = Action.by_id(action_id)
        if action_obj is None:
            return jsonify({
                "result": "error",
                "message": f"Action not found: {action_id}",
            }), 400

        seen.add(action_id)
        action_list.append(action_obj)

    role.actions = action_list
    role.save()

    UserSession.expire_sessions_by_role(role.id)

    return jsonify({
        "result": "success",
        "message": "Actions updated",
        "role": role.to_dict(),
    }), 200


@bp.route("/", methods=["GET"])
def list_roles():
    roles = Role.all()
    return jsonify({
        "result": "success",
        "message": [r.to_dict() for r in roles],
    }), 200


@bp.route("/", methods=["POST"])
def create_role():
    data = request.get_json() or {}
    name = sanitize(data.get("id", None))
    description = data.get("description", None)
    actions = data.get("actions", [])

    if not name or not description:
        return jsonify({
            "result": "error",
            "message": "Missing 'id' or 'description'  field",
        }), 400

    if Role.by_id(name):
        return jsonify({
            "result": "error",
            "message": "Role already exists",
        }), 409

    role_obj = Role(id=name, description=description)
    role_obj.save()

    return add_actions_to_role(name, actions)


@bp.route("/", methods=["PATCH"])
def update_role():
    data = request.get_json() or {}
    name = sanitize(data.get("id", None))
    description = data.get("description", None)
    actions = data.get("actions", [])

    if not name or not description:
        return jsonify({
            "result": "error",
            "message": "Missing 'id' or 'description' field",
        }), 400

    role = Role.by_id(sanitize(name))
    if not role:
        return jsonify({
            "result": "error",
            "message": "Role not found",
        }), 404

    role.description = description
    role.save()

    return add_actions_to_role(name, actions)


@bp.route("/delete", methods=["POST"])
def delete_role():
    data = request.get_json() or {}
    role_name = data.get("id", None)

    role = Role.by_id(sanitize(role_name))
    if not role:
        return jsonify({
            "result": "error",
            "message": "Role not found",
        }), 404

    UserSession.expire_sessions_by_role(role.id)
    role.delete()

    return jsonify({
        "result": "success",
        "message": "Role deleted",
    }), 200