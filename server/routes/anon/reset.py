from flask import request, jsonify, Blueprint, current_app
from models.user import User
from argon2 import PasswordHasher, exceptions as argon_errors
import jwt, datetime
import string, secrets, json, logging

logger = logging.getLogger(__name__)
ph = PasswordHasher()
bp = Blueprint("reset", __name__, url_prefix='/reset')

def send_reset_token(name, token):
    pass

def random_string(length=32):
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(32))

def create_reset_token(user):
    user_obj = User.by_id(user)
    reset_key = current_app.config.get("RESET_SECRET_KEY")
    if user_obj is not None:
        json_data = user_obj.to_dict()
        json_data.pop("twofa_secret")
        json_data.pop("twofa_qr")
        to_hash = json.dumps(json_data)
        hash_string = ph.hash(to_hash)
    else:
        hash_string = ph.hash(random_string())
    payload = {
        "user": user,
        "hash": hash_string,
        "exp": datetime.datetime.utcnow() + datetime.timedelta(minutes=15),
    }
    reset_jwt = jwt.encode(payload, reset_key, "HS256")
    return reset_jwt
    
def verify_reset_token(token):
    reset_key = current_app.config.get("RESET_SECRET_KEY")
    decoded = jwt.decode(token, reset_key, algorithms=["HS256"])
    user_obj = User.by_id(decoded["user"])
    try:
        json_data = user_obj.to_dict()
        json_data.pop("twofa_secret")
        json_data.pop("twofa_qr")
        to_hash = json.dumps(json_data)
        if(ph.verify(decoded["hash"], to_hash)):
            return user_obj
        else:
            return None
    except argon_errors.VerifyMismatchError:
        return None

@bp.route("/request", methods=["POST"])
def request_reset():
    """
    Request a password reset.
    JSON: { "identifier": "<username or email>" }
    Always returns success to avoid user enumeration.
    """
    data = request.get_json(silent=True) or {}
    identifier = (data.get("identifier") or "").strip()

    user = User.by_id(identifier)
    if not user:
        user = User.by_email(email=identifier)
    if user:
        token = create_reset_token(user.id)
        send_reset_token(user.id, token)
    if current_app.config.get("DEBUG"):
        return jsonify({"result": "success", "message": "If the account exists, a reset message has been sent.", "token":token}), 200
    else:
        return jsonify({"result": "success", "message": "If the account exists, a reset message has been sent."}), 200


@bp.route("/confirm", methods=["POST"])
def confirm_reset():
    from utils import check_password_complexity
    """
    Reset the password.
    JSON: { "token": "<token>", "new_password": "<new password>" }
    """
    data = request.get_json(silent=True) or {}
    token = (data.get("token") or "").strip()
    new_pw = (data.get("new_password") or "").strip()

    if not token or not new_pw:
        return jsonify({"result": "error", "message": "Missing token or new password."}), 400

    # Basic password sanity (adjust to your policy)
    valid, errors = check_password_complexity(new_pw)
    if not valid:
        return jsonify({"result": "error", "message": errors}), 400

    try:
        user_obj = verify_reset_token(token)
        if user_obj:
            user_obj.password = new_pw
            return jsonify({"result": "success", "message": "Password changed."}), 201
        else:
            logging.exception("User not found resetting password.")
            return jsonify({"result": "error", "message": "user_not_found"}), 500
    except jwt.ExpiredSignatureError:
        return jsonify({"result": "error", "message": "Reset link expired. Please request a new one."}), 401
    except jwt.InvalidSignatureError:
        return jsonify({"result": "error", "message": "Invalid or stale reset token."}), 400
    except jwt.DecodeError:
        return jsonify({"result": "error", "message": "Decode error."}), 400
    except Exception as e:
        logging.exception("reset confirm failed: %s", e)
        return jsonify({"result": "error", "message": "Unable to reset password."}), 500