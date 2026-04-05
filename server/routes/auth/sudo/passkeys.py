import base64

from flask import Blueprint, jsonify, request

from models.passkey import PassKey

bp = Blueprint("passkeys", __name__, url_prefix="/passkeys")


def b64_to_bytes(s: str) -> bytes:
    s = s.strip()
    s += "=" * (-len(s) % 4)
    return base64.b64decode(s)


@bp.route("/", methods=["GET"])
def list_passkeys():
    items = PassKey.all()
    return jsonify({
        "result": "success",
        "message": [x.to_dict() for x in items],
    })


@bp.route("/delete", methods=["POST"])
def delete_passkey():
    data = request.json or {}

    if "id" not in data:
        return jsonify({
            "result": "error",
            "message": "PassKey id required",
        }), 400

    item = PassKey.by_id(data["id"])
    if not item:
        return jsonify({
            "result": "error",
            "message": "PassKey not found",
        }), 404

    item.delete()

    return jsonify({
        "result": "success",
        "message": "Deleted",
        "deleted_id": data["id"],
    })