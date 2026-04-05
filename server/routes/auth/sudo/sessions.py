from flask import Blueprint, jsonify, request

from models.user_session import UserSession

bp = Blueprint("user_sessions", __name__, url_prefix="/user_sessions")


@bp.route("/", methods=["POST"])
def list_user_sessions_for_user():
    data = request.get_json(silent=True) or {}
    user_name = data.get("id", None)
    output = []

    if user_name:
        user_sessions = UserSession.all_by_user(user_name)
        for user_session in user_sessions:
            item = user_session.to_dict()
            item.pop("user_name", None)
            output.append(item)

        return jsonify({"result": "success", "message": output}), 200

    return jsonify({"result": "success", "message": []}), 200


@bp.route("/expire", methods=["PUT"])
def expire_session():
    data = request.get_json() or {}
    session_id = data.get("id", None)
    token_type = data.get("token_type", None)

    if not session_id or len(session_id) != 32 or token_type not in ["access", "refresh"]:
        return jsonify({"result": "error", "message": "Invalid input"}), 400

    session_obj = UserSession.by_id(session_id)
    if session_obj is None:
        return jsonify({"result": "error", "message": "Session not found"}), 404

    if token_type == "access":
        session_obj.expire()
    else:
        session_obj.expire_refresh()

    return jsonify({
        "result": "success",
        "message": f"Session {session_id} expired.",
    }), 200