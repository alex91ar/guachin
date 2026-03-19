# routes/passkeys.py
import base64
import traceback
from flask import Blueprint, request, jsonify
from flask_jwt_extended import get_jwt

from models.passkey import PassKey
from models.basemodel import db

bp = Blueprint("passkeys", __name__, url_prefix="/passkeys")

def b64_to_bytes(s: str) -> bytes:
    # Handles missing padding too
    s = s.strip()
    s += "=" * (-len(s) % 4)
    return base64.b64decode(s)

@bp.route("/", methods=["GET"])
def list_passkeys():
    items = PassKey.query.all()
    return jsonify({"result": "success", "message": [x.to_dict() for x in items]})

@bp.route("/", methods=["POST"])
def create_passkey():
    data = request.json or {}

    required = ["user_id", "credential_id", "public_key_b64"]
    if not all(k in data for k in required):
        return jsonify({"result": "error", "message": "Missing fields"}), 400

    # avoid duplicates
    existing = PassKey.query.filter_by(credential_id=data["credential_id"]).first()
    if existing:
        return jsonify({"result": "error", "message": "credential_id already exists"}), 409

    try:
        pk_bytes = b64_to_bytes(data["public_key_b64"])
    except Exception:
        return jsonify({"result": "error", "message": "Invalid public_key_b64"}), 400

    item = PassKey(
        user_id=data["user_id"],
        credential_id=str(data["credential_id"]),
        public_key=pk_bytes,
        sign_count=int(data.get("sign_count", 0)),
    )

    db.session.add(item)
    db.session.commit()

    return jsonify({"result": "success", "message": item.to_dict()}), 201

@bp.route("/delete", methods=["POST"])
def delete_passkey():
    data = request.json or {}
    if "id" not in data:
        return jsonify({"result": "error", "message": "PassKey id required"}), 400

    item = PassKey.query.get(data["id"])
    if not item:
        return jsonify({"result": "error", "message": "PassKey not found"}), 404

    item.delete()

    return jsonify({"result": "success", "message": "Deleted", "deleted_id": data["id"]})
