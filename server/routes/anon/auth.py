from flask import request, jsonify, Blueprint, current_app, g, url_for
from flask_jwt_extended import create_access_token,create_refresh_token, jwt_required, get_jwt_identity, get_jwt
from models.user import User
from models.action import Action
from models.user_session import UserSession
from models.passkey import PassKey
from fido2 import cbor
import time
from utils import sanitize_username, check_password_complexity
from flask_jwt_extended.utils import decode_token
from flask_jwt_extended.exceptions import JWTExtendedException
import jwt  # PyJWT exceptions live here too
import uuid
from datetime import datetime
# --- add near the top with imports ---
from fido2.webauthn import AttestedCredentialData,AuthenticatorData 
from fido2.cose import CoseKey
import random
from routes.auth.passkey_user import get_fido2_server, get_rp, b64url_decode, b64url_encode, dict_to_base64, base64_to_dict, jsonify_bytes
from fido2.webauthn import (
    PublicKeyCredentialRpEntity,
    PublicKeyCredentialUserEntity,
    PublicKeyCredentialDescriptor,
    AuthenticatorAttachment,
    UserVerificationRequirement,
)

bp = Blueprint("login", __name__, url_prefix='/login')


def get_raw_token():
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
    else:
        token = None
    return token



@bp.route('/', methods=['POST'])
def login():
    data = request.get_json(silent=True)
    # 2. Must parse JSON with both fields
    if "id" in data and "password" in data:
        password = data["password"]
        id = sanitize_username(data["id"])
        ok, _ = check_password_complexity(data["password"])
        if not ok:
            time.sleep(1)
            return jsonify(result="Error", Message="Invalid Username or Password"), 401
    else:
        time.sleep(1)
        return jsonify(result="Error", Message="Invalid Username or Password"), 401
    s_id = sanitize_username(id)
    if id != s_id:
        time.sleep(1)
        return jsonify(result="Error", Message="Invalid Username or Password"), 401

    # 5. Lookup & verify password
    user_obj = User.by_id(id)
    if not user_obj or not user_obj.verify_password(password):
        time.sleep(1)
        return jsonify(result="Error", Message="Invalid Username or Password"), 401

    # 7. Build JWT payload
    u_sess = UserSession(user_obj)
    u_sess.password = True
    u_sess.save()
    access, refresh = u_sess.get_jwts()
    # 8. Return success
    return jsonify(
        result="success",
        message={
        "access_jwt":access,
        "refresh_jwt":refresh,
        "user_obj":user_obj.to_dict_only_user()}
    ), 200

def get_token_manually():
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None, "Missing or invalid Authorization header"
    return auth_header.split(" ")[1], None

def get_token_claims_manually(token):
    try:
        # Decode and verify signature + expiration
        decoded = decode_token(token)
        return decoded, None  # ✅ token valid

    except jwt.ExpiredSignatureError:
        return None, "token_expired"

    except jwt.InvalidSignatureError:
        return None, "invalid_signature"

    except jwt.DecodeError:
        return None, "malformed_token"

    except JWTExtendedException as e:
        return None, f"JWT error: {str(e)}"

    except Exception as e:
        return None, f"Unexpected error: {str(e)}"

@bp.route('/logout', methods=['POST'])
def logout():
    data = request.get_json(silent=True)
    access_jwt = data.get("access_jwt", None)
    refresh_jwt = data.get("refresh_jwt", None)
    user_name = data.get("user_name", None)
    if access_jwt is None or refresh_jwt is None or user_name is None:
        return jsonify({"result": "error", "message": "Missing required parameters"}), 400 
    try:
        access_jwt_claims, error = get_token_claims_manually(access_jwt)
        if error is not None:
            return jsonify({"result": "error", "message": error}), 422
        refresh_jwt_claims, error = get_token_claims_manually(refresh_jwt)
        if error is not None:
            return jsonify({"result": "error", "message": error}), 422
        access_sub = access_jwt_claims.get("sub", None)
        refresh_sub = refresh_jwt_claims.get("sub", None)
        if access_sub == refresh_sub == user_name:
            session_obj = UserSession.by_id(access_jwt_claims.get("id", None))
            if session_obj:
                session_obj.delete()
            return jsonify({"result": "success", "message": f"localStorage.clear();window.location.href = '{url_for('html_pages.html.home')}';"}), 200
        else:
            return jsonify({"result": "error", "message": "Token sub mismatch."}), 400
    except Exception as e:
        return jsonify({"result": "error", "message": str(e)}), 500

# --- Refresh route --- #
@bp.route('/refresh', methods=['GET'])
@jwt_required(refresh=True)
def refresh():
    try:
        token_obj = UserSession.by_id(get_jwt().get("id", None))
        if not token_obj or not token_obj.is_valid_refresh():
            return jsonify({
            "result": "error",
            "message": "refresh_token_expired"
            }), 401
        user_obj = token_obj.user
        if not user_obj:
            return jsonify(result="error", message="User not found"), 404
        token_obj.refresh_tokens()
        access_token, refresh_token = token_obj.get_jwts()
        return jsonify({"result":"success", "access_jwt":access_token, "refresh_jwt":refresh_token, "user_obj":user_obj.to_dict()}), 200

    except Exception as e:
        return jsonify(result="error", message=str(e)), 401

@bp.route('/signup', methods=['POST'])
def signup():
    try:
        data = request.get_json(silent=True) or {}

        # --- Validate required fields ---
        username = data.get("id", "").strip()
        password = data.get("password", "").strip()
        email = data.get("email", "").strip()

        if not username or not password or not email:
            return jsonify({"result": "error", "message": "Username, password, and email are required."}), 400

        # --- Sanitize username ---
        try:
            username = sanitize_username(username)
        except ValueError as e:
            return jsonify({"result": "error", "message": f"Invalid username: {str(e)}"}), 400

        # --- Validate password complexity ---
        ok, errors = check_password_complexity(password)
        if not ok:
            return jsonify({
                "result": "error",
                "message": "Password not complex enough:\n" + "\n".join(errors)
            }), 400

        # --- Check for existing username or email ---
        if User.by_id(username):
            return jsonify({"result": "error", "message": "Username already exists."}), 409
        else:
            if User.by_email(email):
                return jsonify({"result": "error", "message": f"A user with email '{email}' already exists"}), 409
        # --- Create user ---
        new_user = User(id=username, email=email)
        new_user.set_password(password)
        new_user.add_role("user")
        new_user.save()

        # --- Issue tokens ---
        access, refresh = UserSession(new_user).get_jwts()

        return jsonify({
            "result": "success",
            "message": "Account created successfully.",
            "access_jwt": access,
            "refresh_jwt": refresh,
            "user_obj": new_user.to_dict()
        }), 201

    except Exception as e:
        return jsonify({"result": "error", "message": str(e)}), 500

# ----------------------------
# Passkey login (authenticate)
# ----------------------------


@bp.route("/passkey/begin", methods=["POST"])
def passkey_login_begin():
    try:
        server = get_fido2_server()
        time.sleep(random.uniform(0.35, 0.65))
        data = request.get_json(silent=True) or {}
        username = (data.get("username") or "").strip()
        user_obj = User.by_id(username) if username else None
        user_sess = UserSession(user_obj)
        user_sess.save()
        access_jwt, refresh_jwt = user_sess.get_jwts()
        # Avoid user enumeration: if user doesn't exist, return a fake challenge
        if not user_obj:
            fake_auth_data, _fake_state = server.authenticate_begin(
                [],
                user_verification=UserVerificationRequirement.PREFERRED,
            )
            # IMPORTANT: match your JS expectation -> wrap in {"public_key": ...}
            return jsonify({"result": "success", "public_key": jsonify_bytes(fake_auth_data), "message":{
            "access_jwt":access_jwt,
            "refresh_jwt":refresh_jwt,
            "user_obj":user_obj.to_dict_only_user()}}), 200

        # Build allowCredentials using BYTES ids
        credentials = [
            PublicKeyCredentialDescriptor(
                id=b64url_decode(pk.credential_id),  # ✅ bytes
                type="public-key",
            )
            for pk in user_obj.passkeys
        ]

        # If user has no passkeys, still return a fake challenge
        if not credentials:
            fake_auth_data, _fake_state = server.authenticate_begin(
                [],
                user_verification=UserVerificationRequirement.PREFERRED,
            )
            return jsonify({"result": "success", "public_key": jsonify_bytes(fake_auth_data), "message":{
            "access_jwt":access_jwt,
            "refresh_jwt":refresh_jwt,
            "user_obj":user_obj.to_dict_only_user()}}), 200

        auth_data, state = server.authenticate_begin(
            credentials,
            user_verification=UserVerificationRequirement.PREFERRED,
        )

        user_obj.fido2_state = dict_to_base64(state)
        user_obj.fido2_state_timestamp = datetime.utcnow()
        user_obj.save()

        # 7. Build JWT payload
        
        
        # ✅ wrap in {"public_key": ...} to match your JS
        return jsonify({"result": "success", "public_key": jsonify_bytes(auth_data), "message":{
            "access_jwt":access_jwt,
            "refresh_jwt":refresh_jwt,
            "user_obj":user_obj.to_dict_only_user()}}), 200

    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return jsonify({
            "result": "error",
            "message": "Exception during login begin: " + type(e).__name__ + " " + str(e)
        }), 500

