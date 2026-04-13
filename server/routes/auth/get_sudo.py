from flask import Blueprint, current_app, jsonify, request
from flask_jwt_extended import get_jwt, get_jwt_identity

from models.user import User
from models.user_session import UserSession

bp = Blueprint("get_sudo", __name__, url_prefix="/get_sudo")


@bp.route("/", methods=["POST"])
def get_sudo():
    user_obj = User.by_id(get_jwt_identity())
    user_session = UserSession.by_id(get_jwt().get("id", None))
    print(f"from get_sudo sudo = {user_session.sudo}. password = {user_session.password}. id = {user_session.id}. passkey = {user_session.passkey}. partial = {user_session.partial}")

    if user_obj is None or user_session is None:
        return jsonify({"result": "error", "message": "session_or_user_not_found"}), 404

    if current_app.config.get("DEBUG") is False and not user_session.is_elevated(user_obj):
        data = request.get_json(silent=True) or {}
        otp = data.get("otp")
        if not otp:
            return jsonify({"result": "error", "message": "2fa_required"}), 400
        if user_obj.verify_2fa(otp) is False:
            return jsonify({"result": "error", "message": "2fa_required"}), 401
    token, refresh_token = user_session.elevate()

    return jsonify(
        result="success",
        message={
            "access_jwt": token,
            "refresh_jwt": refresh_token,
            "user_obj": user_obj.to_dict(),
        },
    ), 200