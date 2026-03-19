from flask import jsonify, Blueprint, request
from models.user_session import UserSession

bp = Blueprint("user_sessions", __name__, url_prefix='/user_sessions')


# ---------------- READ ---------------- #
@bp.route("/", methods=["POST"])
def list_user_sessions_for_user():
    """
    List all actions.
    """
    data = request.get_json(silent=True) or {}
    user_name = data.get("id", None)
    output = []
    if user_name:
        user_sessions = UserSession.by_user_name(user_name)
        for user_session in user_sessions:
            user_session = user_session.to_dict()
            user_session.pop("user_name")
            output.append(user_session)
        return jsonify({"result": "success", "message": output}), 200
    return jsonify({"result":"success","message":[]}), 200

# ---------------------------------------------------- #
# PUT /sessions/expire
# ---------------------------------------------------- #
@bp.route("/expire", methods=["PUT"])
def expire_session():
    try:
        data = request.get_json() or {}
        id = data.get("id", None)
        token_type = data.get("token_type", None)
        if not id or len(id) != 16 or not token_type or token_type not in ["access", "refresh"]:
            return jsonify({"result": "error", "message": "Invalid input"}), 400
        session_obj = UserSession.by_id(id)
        if session_obj is None:
            return jsonify({"result": "error", "message": "Session not found"}), 404
        if token_type == "access":
            session_obj.expire()
        else:
            session_obj.expire_refresh()
        return jsonify({"result": "success", "message": f"Session {id} expired."}), 200

    except Exception as e:
        return jsonify({"result": "error", "message": str(e)}), 500