from __future__ import annotations

import datetime
import json
import logging
import secrets
import string

import jwt
from argon2 import PasswordHasher, exceptions as argon_errors
from flask import Blueprint, current_app, jsonify, request

from models.user import User

logger = logging.getLogger(__name__)
ph = PasswordHasher()
bp = Blueprint("reset", __name__, url_prefix="/reset")


def send_reset_token(name, token):
    pass


def random_string(length=32):
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def create_reset_token(user):
    user_obj = User.by_id(user)
    reset_key = current_app.config.get("RESET_SECRET_KEY")

    if user_obj is not None:
        json_data = user_obj.to_dict()
        json_data.pop("twofa_secret", None)
        json_data.pop("twofa_qr", None)
        to_hash = json.dumps(json_data, sort_keys=True)
        hash_string = ph.hash(to_hash)
    else:
        hash_string = ph.hash(random_string())

    payload = {
        "user": user,
        "hash": hash_string,
        "exp": datetime.datetime.utcnow() + datetime.timedelta(minutes=15),
    }
    return jwt.encode(payload, reset_key, algorithm="HS256")


def verify_reset_token(token):
    reset_key = current_app.config.get("RESET_SECRET_KEY")
    decoded = jwt.decode(token, reset_key, algorithms=["HS256"])

    user_obj = User.by_id(decoded["user"])
    if user_obj is None:
        return None

    try:
        json_data = user_obj.to_dict()
        json_data.pop("twofa_secret", None)
        json_data.pop("twofa_qr", None)
        to_hash = json.dumps(json_data, sort_keys=True)

        if ph.verify(decoded["hash"], to_hash):
            return user_obj
        return None
    except argon_errors.VerifyMismatchError:
        return None


@bp.route("/request", methods=["POST"])
def request_reset():
    data = request.get_json(silent=True) or {}
    identifier = (data.get("identifier") or "").strip()

    user = User.by_id(identifier)
    if not user:
        user = User.by_email(identifier)

    token = None
    if user:
        token = create_reset_token(user.id)
        send_reset_token(user.id, token)

    if current_app.config.get("DEBUG"):
        return jsonify({
            "result": "success",
            "message": "If the account exists, a reset message has been sent.",
            "token": token,
        }), 200

    return jsonify({
        "result": "success",
        "message": "If the account exists, a reset message has been sent.",
    }), 200


@bp.route("/confirm", methods=["POST"])
def confirm_reset():
    from utils import check_password_complexity

    data = request.get_json(silent=True) or {}
    token = (data.get("token") or "").strip()
    new_pw = (data.get("new_password") or "").strip()

    if not token or not new_pw:
        return jsonify({"result": "error", "message": "Missing token or new password."}), 400

    valid, errors = check_password_complexity(new_pw)
    if not valid:
        return jsonify({"result": "error", "message": errors}), 400

    user_obj = verify_reset_token(token)
    if user_obj:
        ok, pw_errors = user_obj.set_password(new_pw)
        if not ok:
            return jsonify({"result": "error", "message": pw_errors}), 400
        user_obj.save()
        return jsonify({"result": "success", "message": "Password changed."}), 201

    logger.exception("User not found resetting password.")
    return jsonify({"result": "error", "message": "user_not_found"}), 500