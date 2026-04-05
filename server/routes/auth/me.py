from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt, get_jwt_identity
import traceback

from models.log import Log
from models.user import User
from models.user_session import UserSession

bp = Blueprint("me", __name__, url_prefix="/me")


@bp.route("/2fa", methods=["POST"])
def login_twofa():
    data = request.get_json(silent=True) or {}
    if "otp" not in data:
        return jsonify({"result": "error", "message": "Missing required parameters"}), 400

    otp = data.get("otp")
    claims = get_jwt()
    user_obj = User.by_id(claims.get("sub", None))
    if not user_obj:
        return jsonify(result="error", message="User not found"), 404

    user_sess = UserSession.by_id(get_jwt().get("id", None))
    if user_sess is None:
        return jsonify({"result": "error", "message": "Session not found"}), 404

    if user_obj.twofa_enabled is False or user_obj.verify_2fa(otp):
        user_sess.sudo = True
        user_sess.partial = False
        user_sess.save()

        access_jwt, refresh_jwt = user_sess.get_jwts()
        UserSession.clear_partial_sessions(user_obj.id)

        return jsonify({
            "result": "success",
            "message": {
                "access_jwt": access_jwt,
                "refresh_jwt": refresh_jwt,
                "user_obj": user_obj.to_dict(),
            },
        }), 200

    UserSession.clear_partial_sessions(user_obj.id)
    return jsonify({"result": "error", "message": "invalid_otp"}), 401


@bp.route("/", methods=["GET"])
def me():
    user_id = get_jwt_identity()
    user = User.by_id(user_id)
    if not user:
        return jsonify({"result": "error", "message": "User not found"}), 404

    return jsonify({"result": "success", "message": user.to_dict()}), 200


@bp.route("/am_i_admin", methods=["GET"])
def am_i_admin():
    claims = get_jwt()
    return jsonify({"result": "success", "message": claims.get("sudo", False)}), 200


@bp.route("/2fa", methods=["GET"])
def twofa():
    user_id = get_jwt_identity()
    user = User.by_id(user_id)
    if not user:
        return jsonify({"result": "error", "message": "User not found"}), 404

    data = user.get_2fa_data()
    return jsonify({"result": "success", "message": data}), 200


@bp.route("/sessions", methods=["GET"])
def sessions():
    user_id = get_jwt_identity()
    user_sessions = list(UserSession.all_by_user(user_id))
    if not user_sessions:
        return jsonify({"result": "error", "message": "User not found"}), 404

    data = []
    for user_session in user_sessions:
        item = user_session.to_dict()
        item.pop("user_name", None)
        data.append(item)

    return jsonify({"result": "success", "message": data}), 200


@bp.route("/sessions/expire", methods=["PUT"])
def expire_session():
    data = request.get_json() or {}
    session_id = data.get("id", None)
    token_type = data.get("token_type", None)

    if not session_id or len(session_id) != 32 or token_type not in ["access", "refresh"]:
        return jsonify({"result": "error", "message": "Invalid input"}), 400

    user_id = get_jwt_identity()
    session_obj = UserSession.by_id(session_id)
    if session_obj is None or session_obj.user_id != user_id:
        return jsonify({"result": "error", "message": "Session not found"}), 404

    if token_type == "access":
        session_obj.expire()
    else:
        session_obj.expire_refresh()

    return jsonify({"result": "success", "message": f"Session {session_id} expired."}), 200


@bp.route("/update_password", methods=["PUT"])
def update_password():
    data = request.get_json() or {}
    old_password = data.get("old_password")
    new_password = data.get("new_password")

    if not old_password or not new_password:
        return jsonify({"result": "error", "message": "Both old and new passwords are required."}), 400
    if not isinstance(old_password, str) or not isinstance(new_password, str):
        return jsonify({"result": "error", "message": "Passwords must be strings."}), 422

    user = User.by_id(get_jwt_identity())
    if not user:
        return jsonify({"result": "error", "message": "User not found."}), 404

    if not user.verify_password(old_password):
        return jsonify({"result": "error", "message": "Invalid old password."}), 401

    ok, errors = user.set_password(new_password)
    if not ok:
        return jsonify({"result": "error", "message": errors}), 400
    user.save()
    return jsonify({"result": "success", "message": "Password updated successfully."}), 200


@bp.route("/update_details", methods=["PUT"])
def update_details():
    data = request.get_json() or {}
    user = User.by_id(get_jwt_identity())
    if not user:
        return jsonify({"result": "error", "message": "User not found"}), 404

    email = data.get("email")
    description = data.get("description")

    if email:
        user.email = email
    if description:
        user.description = description

    user.save()

    return jsonify({"result": "success", "message": "Details updated successfully."}), 200


@bp.route("/enable_2fa", methods=["PUT"])
def enable_2fa():
    user = User.by_id(get_jwt_identity())
    if not user:
        return jsonify({"result": "error", "message": "User not found"}), 404

    if user.twofa_enabled:
        return jsonify({"result": "error", "message": "Two factor already enabled"}), 409

    payload = request.get_json() or {}
    otp = payload.get("otp", "")
    if not isinstance(otp, str) or len(otp) != 6:
        return jsonify({"result": "error", "message": "invalid_otp"}), 400

    if user.enable_2fa(otp):
        user_sess = UserSession.by_id(get_jwt().get("id", None))
        if user_sess is None:
            return jsonify({"result": "error", "message": "Session not found"}), 404

        user_sess.sudo = True
        user_sess.passkey = True
        user_sess.save()

        access_jwt, refresh_jwt = user_sess.get_jwts()

        return jsonify({
            "result": "success",
            "message": "2FA enabled successfully.",
            "access_jwt": access_jwt,
            "refresh_jwt": refresh_jwt,
        }), 202

    return jsonify({"result": "error", "message": "invalid_otp"}), 401


@bp.route("/disable_2fa", methods=["PUT"])
def disable_2fa():
    payload = request.get_json() or {}
    otp = payload.get("otp")
    if not otp:
        return jsonify({"result": "error", "message": "invalid_otp"}), 400

    user = User.by_id(get_jwt_identity())
    if not user:
        return jsonify({"result": "error", "message": "User not found"}), 404
    if not user.twofa_enabled:
        return jsonify({"result": "error", "message": "Two factor not enabled"}), 406
    if not user.disable_2fa(otp):
        return jsonify({"result": "error", "message": "invalid_otp"}), 401

    return jsonify({"result": "success", "message": "2FA disabled successfully."}), 202


@bp.route("/get_logs", methods=["GET"])
def get_user_logs():
    user_id = get_jwt_identity()
    logs = Log.all_by_user(user_id)
    return jsonify({"result": "success", "message": [r.to_dict() for r in logs]}), 200


@bp.route("/purge", methods=["GET"])
def purge_all_logs():
    user_id = get_jwt_identity()
    logs = Log.all_by_user(user_id)
    for log in logs:
        log.delete()
    return jsonify({"result": "success", "message": "Logs purged"}), 200