from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, get_jwt
from models.user import User
from models.user_session import UserSession
from models.log import Log
import traceback
bp = Blueprint("me", __name__, url_prefix="/me")



@bp.route("/2fa", methods=["POST"])
def login_twofa():
    data = request.get_json(silent=True)
    if "otp" not in data:
        return jsonify({"result": "error", "message": "Missing required parameters"}), 400 
    otp = data.get("otp", None)
    claims = get_jwt()
    user_obj = User.by_id(claims.get('sub',None))
    if not user_obj:
        return jsonify(result="error", message="User not found"), 404
    if user_obj.twofa_enabled == False or user_obj.verify_2fa(otp):
        user_sess = UserSession.by_id(get_jwt().get("id", None))
        user_sess.sudo = True
        user_sess.save()
        access_jwt, refresh_jwt = user_sess.get_jwts()
        UserSession.clear_partial_sessions(id)
        return jsonify({"result": "success", "message": {"access_jwt":access_jwt, "refresh_jwt":refresh_jwt, "user_obj":user_obj.to_dict()}}), 200
    else:
        UserSession.clear_partial_sessions()
        return jsonify({"result": "error", "message": "invalid_otp"}), 401

# ---------------------------------------------------- #
# GET /me
# ---------------------------------------------------- #
@bp.route("/", methods=["GET"])
def me():
    try:
        id = get_jwt_identity()
        user = User.by_id(id)
        if not user:
            return jsonify({"result": "error", "message": "User not found"}), 404
        data = user.to_dict()
        return jsonify({"result": "success", "message": data}), 200

    except Exception as e:
        return jsonify({"result": "error", "message": str(e)}), 500

@bp.route("/am_i_admin", methods=["GET"])
def am_i_admin():
    claims = get_jwt()
    return jsonify({"result:":"success", "message":claims.get("sudo", False)}), 200

# ---------------------------------------------------- #
# GET /2fa
# ---------------------------------------------------- #
@bp.route("/2fa", methods=["GET"])
def twofa():
    try:
        id = get_jwt_identity()
        user = User.by_id(id)
        if not user:
            return jsonify({"result": "error", "message": "User not found"}), 404

        data = user.get_2fa_data()
        return jsonify({"result": "success", "message": data}), 200

    except Exception as e:
        return jsonify({"result": "error", "message": str(e)}), 500

# ---------------------------------------------------- #
# GET /sessions
# ---------------------------------------------------- #
@bp.route("/sessions", methods=["GET"])
def sessions():
    try:
        id = get_jwt_identity()
        user_sessions = UserSession.by_user_name(id)
        if not user_sessions:
            return jsonify({"result": "error", "message": "User not found"}), 404

        data = []
        for user_session in user_sessions:
            user_session = user_session.to_dict()
            user_session.pop("user_name")
            data.append(user_session)
        return jsonify({"result": "success", "message": data}), 200

    except Exception as e:
        return jsonify({"result": "error", "message": traceback.format_exc()}), 500

# ---------------------------------------------------- #
# PUT /sessions/expire
# ---------------------------------------------------- #
@bp.route("/sessions/expire", methods=["PUT"])
def expire_session():
    try:
        data = request.get_json() or {}
        id = data.get("id", None)
        token_type = data.get("token_type", None)
        if not id or len(id) != 32 or not token_type or token_type not in ["access", "refresh"]:
            return jsonify({"result": "error", "message": "Invalid input"}), 400
        user_id = get_jwt_identity()
        session_obj = UserSession.by_id(id)
        if session_obj.user_id != user_id or session_obj is None:
            return jsonify({"result": "error", "message": "Session not found"}), 404
        if token_type == "access":
            session_obj.expire()
        else:
            session_obj.expire_refresh()
        return jsonify({"result": "success", "message": f"Session {id} expired."}), 200

    except Exception as e:
        return jsonify({"result": "error", "message": traceback.format_exc()}), 500


# ---------------------------------------------------- #
# PUT /me/update_password
# ---------------------------------------------------- #
@bp.route("/update_password", methods=["PUT"])
def update_password():
    try:
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

        user.password = new_password
        user.save()
        return jsonify({"result": "success", "message": "Password updated successfully."}), 200

    except ValueError as ve:
        return jsonify({"result": "error", "message": str(ve)}), 400
    except Exception as e:
        return jsonify({"result": "error", "message": str(e)}), 500


# ---------------------------------------------------- #
# PUT /me/update_details
# ---------------------------------------------------- #
@bp.route("/update_details", methods=["PUT"])
def update_details():
    try:
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

    except ValueError as ve:
        return jsonify({"result": "error", "message": str(ve)}), 400
    except Exception as e:
        return jsonify({"result": "error", "message": str(e)}), 500


# ---------------------------------------------------- #
# PUT /me/enable_2fa
# ---------------------------------------------------- #
@bp.route("/enable_2fa", methods=["PUT"])
def enable_2fa():
    try:
        user = User.by_id(get_jwt_identity())
        if not user:
            return jsonify({"result": "error", "message": "User not found"}), 404

        if user.twofa_enabled:
            return jsonify({"result":"error","message":"Two factor already enabled"}), 409
        otp = request.get_json().get("otp", "")
        if not isinstance(otp, str) or len(otp) != 6:
            return jsonify({"result": "error", "message": "invalid_otp"}), 400
        if user.enable_2fa(otp):
            user_sess = UserSession.by_id(get_jwt().get("id", None))
            user_sess.sudo = True
            user_sess.twofa = True
            user_sess.save()
            access_jwt, refresh_jwt = user_sess.get_jwts()
            return jsonify({"result": "success", "message": "2FA enabled successfully.", "access_jwt": access_jwt, "refresh_jwt":refresh_jwt}), 202
        return jsonify({"result": "error", "message": "invalid_otp"}), 401

    except Exception as e:
        return jsonify({"result": "error", "message": str(e)}), 500


# ---------------------------------------------------- #
# PUT /me/disable_2fa
# ---------------------------------------------------- #
@bp.route("/disable_2fa", methods=["PUT"])
def disable_2fa():
    try:
        otp = request.get_json().get("otp")
        if not otp:
            return jsonify({"result": "error", "message": "invalid_otp"}), 400

        user = User.by_id(get_jwt_identity())
        if not user:
            return jsonify({"result": "error", "message": "User not found"}), 404
        if not user.twofa_enabled:
            return jsonify({"result":"error","message":"Two factor not enabled"}), 406
        if not user.disable_2fa(otp):
            return jsonify({"result": "error", "message": "invalid_otp"}), 401

        return jsonify({"result": "success", "message": "2FA disabled successfully."}), 202

    except Exception as e:
        return jsonify({"result": "error", "message": str(e)}), 500


@bp.route("/get_logs", methods=["GET"])
def get_user_logs():
    return jsonify({"result":"success","message":[r.to_dict() for r in Log.all_by_user(user=get_jwt_identity())]}), 200
 
@bp.route("/purge", methods=["GET"])
def purge_all_logs():
    return jsonify({"result":"success","message":[r.delete() for r in Log.all_by_user(user=get_jwt_identity())]}), 200
