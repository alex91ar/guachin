from __future__ import annotations

import random
import time
from datetime import datetime, timezone

import jwt
from fido2.webauthn import PublicKeyCredentialDescriptor, UserVerificationRequirement
from flask import Blueprint, jsonify, make_response, request, url_for
from flask_jwt_extended import get_jwt, jwt_required
from flask_jwt_extended.exceptions import JWTExtendedException
from flask_jwt_extended.utils import decode_token

from models.passkey import PassKey
from models.user import User
from models.user_session import UserSession
from routes.auth.passkey_user import (
    b64url_decode,
    dict_to_base64,
    get_fido2_server,
    jsonify_bytes,
)
from utils import check_password_complexity, sanitize_username

bp = Blueprint("login", __name__, url_prefix="/login")


def get_token_manually():
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None, "Missing or invalid Authorization header"
    return auth_header.split(" ")[1], None


def get_token_claims_manually(token):
    try:
        decoded = decode_token(token)
        return decoded, None
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


@bp.route("/", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}

    if "id" not in data or "password" not in data:
        time.sleep(1)
        return jsonify(result="Error", Message="Invalid Username or Password"), 401

    password = data["password"]
    user_id = sanitize_username(data["id"])

    ok, _ = check_password_complexity(password)
    if not ok:
        time.sleep(1)
        return jsonify(result="Error", Message="Invalid Username or Password"), 401

    sanitized_id = sanitize_username(user_id)
    if user_id != sanitized_id:
        time.sleep(1)
        return jsonify(result="Error", Message="Invalid Username or Password"), 401

    user_obj = User.by_id(user_id)
    if not user_obj or not user_obj.verify_password(password):
        time.sleep(1)
        return jsonify(result="Error", Message="Invalid Username or Password"), 401

    u_sess = UserSession(user_obj)
    u_sess.password = True
    u_sess.save()

    access, refresh = u_sess.get_jwts()

    return jsonify(
        result="success",
        message={
            "access_jwt": access,
            "refresh_jwt": refresh,
            "user_obj": user_obj.to_dict_only_user(),
        },
    ), 200


@bp.route("/logout", methods=["POST"])
def logout():
    data = request.get_json(silent=True) or {}
    access_jwt = data.get("access_jwt")
    refresh_jwt = data.get("refresh_jwt")
    user_name = data.get("user_name")

    if access_jwt is None or refresh_jwt is None or user_name is None:
        return jsonify({"result": "error", "message": "Missing required parameters"}), 400

    access_jwt_claims, error = get_token_claims_manually(access_jwt)
    if error is not None:
        return jsonify({"result": "error", "message": error}), 422

    refresh_jwt_claims, error = get_token_claims_manually(refresh_jwt)
    if error is not None:
        return jsonify({"result": "error", "message": error}), 422

    access_sub = access_jwt_claims.get("sub")
    refresh_sub = refresh_jwt_claims.get("sub")

    if access_sub == refresh_sub == user_name:
        session_obj = UserSession.by_id(access_jwt_claims.get("id"))
        if session_obj:
            session_obj.delete()

        resp = make_response(jsonify({
            "result": "success",
            "message": f"localStorage.clear();window.location.href = '{url_for('html_pages.html.home')}';",
        }), 200)
        resp.delete_cookie("jwt_cookie")
        resp.delete_cookie("session")
        return resp

    return jsonify({"result": "error", "message": "Token sub mismatch."}), 400


@bp.route("/refresh", methods=["GET"])
@jwt_required(refresh=True)
def refresh():
    token_obj = UserSession.by_id(get_jwt().get("id"))
    if not token_obj or not token_obj.is_valid_refresh():
        return jsonify({
            "result": "error",
            "message": "refresh_token_expired",
        }), 401

    user_obj = User.by_id(token_obj.user_id)
    if not user_obj:
        return jsonify(result="error", message="User not found"), 404

    token_obj.refresh_tokens()
    access_token, refresh_token = token_obj.get_jwts()

    return jsonify({
        "result": "success",
        "access_jwt": access_token,
        "refresh_jwt": refresh_token,
        "user_obj": user_obj.to_dict(),
    }), 200


@bp.route("/signup", methods=["POST"])
def signup():
    data = request.get_json(silent=True) or {}

    username = data.get("id", "").strip()
    password = data.get("password", "").strip()
    email = data.get("email", "").strip()

    if not username or not password or not email:
        return jsonify({
            "result": "error",
            "message": "Username, password, and email are required.",
        }), 400

    try:
        username = sanitize_username(username)
    except ValueError as e:
        return jsonify({"result": "error", "message": f"Invalid username: {str(e)}"}), 400

    ok, errors = check_password_complexity(password)
    if not ok:
        return jsonify({
            "result": "error",
            "message": "Password not complex enough:\n" + "\n".join(errors),
        }), 400

    if User.by_id(username):
        return jsonify({"result": "error", "message": "Username already exists."}), 409

    if User.by_email(email):
        return jsonify({
            "result": "error",
            "message": f"A user with email '{email}' already exists",
        }), 409

    new_user = User(id=username, email=email)

    ok, errors = new_user.set_password(password)
    if not ok:
        return jsonify({
            "result": "error",
            "message": "Password not complex enough:\n" + "\n".join(errors),
        }), 400

    new_user.add_role("user")
    new_user.save()

    user_session = UserSession(new_user, is_signup=True)
    user_session.save()

    access, refresh = user_session.get_jwts()

    return jsonify({
        "result": "success",
        "message": "Account created successfully.",
        "access_jwt": access,
        "refresh_jwt": refresh,
        "user_obj": new_user.to_dict(),
    }), 201


@bp.route("/passkey/begin", methods=["POST"])
def passkey_login_begin():
    server = get_fido2_server()
    time.sleep(random.uniform(0.35, 0.65))

    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    user_obj = User.by_id(username) if username else None

    if user_obj is not None:
        user_sess = UserSession(user_obj)
        user_sess.save()
        access_jwt, refresh_jwt = user_sess.get_jwts()
        user_obj_payload = user_obj.to_dict_only_user()
    else:
        access_jwt = None
        refresh_jwt = None
        user_obj_payload = None

    if not user_obj:
        fake_auth_data, _fake_state = server.authenticate_begin(
            [],
            user_verification=UserVerificationRequirement.PREFERRED,
        )
        return jsonify({
            "result": "success",
            "public_key": jsonify_bytes(fake_auth_data),
            "message": {
                "access_jwt": access_jwt,
                "refresh_jwt": refresh_jwt,
                "user_obj": user_obj_payload,
            },
        }), 200

    credentials = [
        PublicKeyCredentialDescriptor(
            id=b64url_decode(pk.id),
            type="public-key",
        )
        for pk in getattr(user_obj, "passkeys", [])
    ]

    if not credentials:
        fake_auth_data, _fake_state = server.authenticate_begin(
            [],
            user_verification=UserVerificationRequirement.PREFERRED,
        )
        return jsonify({
            "result": "success",
            "public_key": jsonify_bytes(fake_auth_data),
            "message": {
                "access_jwt": access_jwt,
                "refresh_jwt": refresh_jwt,
                "user_obj": user_obj_payload,
            },
        }), 200

    auth_data, state = server.authenticate_begin(
        credentials,
        user_verification=UserVerificationRequirement.PREFERRED,
    )

    user_obj.fido2_state = dict_to_base64(state)
    user_obj.fido2_state_timestamp = datetime.now(timezone.utc)
    user_obj.save()

    return jsonify({
        "result": "success",
        "public_key": jsonify_bytes(auth_data),
        "message": {
            "access_jwt": access_jwt,
            "refresh_jwt": refresh_jwt,
            "user_obj": user_obj_payload,
        },
    }), 200