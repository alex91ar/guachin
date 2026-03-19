from flask import Blueprint, jsonify,current_app, request
from flask_jwt_extended import get_jwt_identity, get_jwt

from routes.anon.auth import get_raw_token
from models.user import User
from models.user_session import UserSession

bp = Blueprint("get_sudo", __name__,url_prefix='/get_sudo')

# ---------------- READ ---------------- #
@bp.route("/", methods=["POST"])
def get_sudo():
    """
    Gets an instant sudo token when debug is on.
    Upgrades your JWT token to a SUDO token, given a correct OTP. When debug is off.
    """
    user_obj = User.by_id(get_jwt_identity())
    user_session = UserSession.by_id(get_jwt().get("id", None))

    if current_app.config.get("DEBUG") == False and not user_session.is_elevated():
        data = request.get_json(silent=True)
        if not data or "otp" not in data:
            return jsonify({"result":"error", "message":"2fa_required"})
        if user_obj.verify_2fa(data["otp"]) == False :
            return jsonify({"result":"error", "message": "2fa_required"}), 401
    
    token, refresh_token = user_session.elevate()
    

    # 8. Return success
    return jsonify(
        result="success",
        message={
        "access_jwt":token,
        "refresh_jwt":refresh_token,
        "user_obj":user_obj.to_dict()}
    ), 200
