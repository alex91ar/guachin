from __future__ import annotations

import base64
import dataclasses
import json
import struct
from datetime import datetime, timezone

import cbor2 as cbor
from flask import Blueprint, current_app, jsonify, request
from flask_jwt_extended import get_jwt, get_jwt_identity
from fido2.cose import CoseKey
from fido2.utils import websafe_decode as b64url_decode
from fido2.webauthn import (
    AttestedCredentialData,
    AuthenticatorAttachment,
    AuthenticatorData,
    PublicKeyCredentialDescriptor,
    PublicKeyCredentialRpEntity,
    PublicKeyCredentialUserEntity,
    UserVerificationRequirement,
)

from models.passkey import PassKey
from models.user import User
from models.user_session import UserSession
from models.basemodel import get_session
bp = Blueprint("passkeys", __name__, url_prefix="/passkeys")


def get_rp() -> PublicKeyCredentialRpEntity:
    domain = current_app.config["DOMAIN"]
    return PublicKeyCredentialRpEntity(name=domain, id=domain)


def b64url_encode(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode("ascii")


def dict_to_base64(d):
    json_str = json.dumps(d)
    b64_bytes = base64.b64encode(json_str.encode("utf-8"))
    return b64_bytes.decode("ascii")


def base64_to_dict(b64_str):
    json_bytes = base64.b64decode(b64_str)
    return json.loads(json_bytes.decode("utf-8"))


def get_fido2_server():
    return current_app.extensions["fido2_server"]


def jsonify_bytes(obj):
    if dataclasses.is_dataclass(obj):
        return jsonify_bytes(dataclasses.asdict(obj))
    if isinstance(obj, dict):
        return {k: jsonify_bytes(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [jsonify_bytes(v) for v in obj]
    if isinstance(obj, bytes):
        return base64.urlsafe_b64encode(obj).rstrip(b"=").decode("ascii")
    if hasattr(obj, "value"):
        return obj.value
    return obj


@bp.route("/", methods=["GET"])
def list_passkeys():
    user_id = get_jwt_identity()
    keys = PassKey.all_by_user(user_id)
    return jsonify({
        "result": "success",
        "message": [
            {
                "id": k.id,
                "credential_id": k.id,
                "sign_count": k.sign_count,
            }
            for k in keys
        ],
    })


@bp.route("/register/begin", methods=["POST"])
def register_begin():
    server = get_fido2_server()
    username = get_jwt_identity()
    user_id = username.encode("utf-8")

    user_obj = User.by_id(username)
    if not user_obj:
        return jsonify({"result": "error", "message": "Exception during registration begin."}), 500

    registration_data, state = server.register_begin(
        PublicKeyCredentialUserEntity(
            id=user_id,
            name=username,
            display_name=username,
        ),
        [
            PublicKeyCredentialDescriptor(
                id=b64url_decode(passkey.id),
                type="public-key",
            )
            for passkey in getattr(user_obj, "passkeys", [])
        ],
        user_verification=UserVerificationRequirement.PREFERRED,
        authenticator_attachment=AuthenticatorAttachment.PLATFORM,
    )
    user_obj.fido2_state = dict_to_base64(state)
    user_obj.fido2_state_timestamp = datetime.now(timezone.utc)
    user_obj.save()

    return jsonify(jsonify_bytes(registration_data))


@bp.route("/register/complete", methods=["POST"])
def passkey_register_complete():
    db_session = get_session()
    user_id = get_jwt_identity()
    data = request.get_json(force=True)
    user_obj = User.by_id(user_id, db_session)
    if not user_obj:
        return jsonify({"result": "error", "message": "Exception during registration begin."}), 500

    server = get_fido2_server()
    state = base64_to_dict(user_obj.fido2_state)

    response = data.copy()
    resp_obj = response["response"].copy()
    resp_obj["clientDataJSON"] = b64url_decode(resp_obj["clientDataJSON"])
    resp_obj["attestationObject"] = b64url_decode(resp_obj["attestationObject"])
    response["response"] = resp_obj

    auth_data = server.register_complete(state, response=response)

    cred_data = auth_data.credential_data
    credential_id_b64u = b64url_encode(cred_data.credential_id)
    print(credential_id_b64u)
    print("[************************************************************************************************************************************************]")
    print("[************************************************************************************************************************************************]")
    print("[************************************************************************************************************************************************]")
    print("[************************************************************************************************************************************************]")
    print("[************************************************************************************************************************************************]")
    print("[************************************************************************************************************************************************]")
    print("[************************************************************************************************************************************************]")
    print("[************************************************************************************************************************************************]")
    print("[************************************************************************************************************************************************]")
    print("[************************************************************************************************************************************************]")
    pk = PassKey(
        user_id=user_obj.id,
        id=credential_id_b64u,
        public_key=cbor.dumps(cred_data.public_key),
        credential_data=bytes(cred_data),
        sign_count=auth_data.counter or 0,
    )
    pk.save(session=db_session)

    user_obj.fido2_state = None
    user_obj.fido2_state_timestamp = None
    user_obj.save(session=db_session)
    db_session.close()

    return jsonify({"result": "success", "message": {"status": "ok"}})


@bp.route("/login/complete", methods=["POST"])
def passkey_login_complete():
    db_session = get_session()
    try:
        data = request.get_json(force=True) or {}
        username = (data.get("username") or "").strip()

        user_obj = User.by_id(username, db_session) if username else None
        if not user_obj or not user_obj.fido2_state:
            UserSession.clear_partial_sessions(username, db_session)
            return jsonify({"result": "error", "message": "Invalid or expired login attempt."}), 400

        server = get_fido2_server()
        state = base64_to_dict(user_obj.fido2_state)

        cred_id_b64u = (data.get("rawId") or data.get("id") or "").strip()
        if not cred_id_b64u:
            return jsonify({"result": "error", "message": "Missing credential id."}), 400

        pk = PassKey.by_credential_id(user_obj.id, cred_id_b64u, db_session)
        if not pk:
            return jsonify({"result": "error", "message": "Unknown passkey."}), 400

        cred_id_bytes = b64url_decode(cred_id_b64u)
        cose_key_cbor = pk.public_key
        cose_key_map = cbor.loads(cose_key_cbor)
        _public_key = CoseKey.parse(cose_key_map)

        aaguid = getattr(pk, "aaguid", None)
        if aaguid:
            aaguid_bytes = aaguid if isinstance(aaguid, (bytes, bytearray)) else bytes.fromhex(aaguid)
            aaguid_bytes = aaguid_bytes[:16].ljust(16, b"\x00")
        else:
            aaguid_bytes = b"\x00" * 16

        credential_data = (
            aaguid_bytes
            + struct.pack(">H", len(cred_id_bytes))
            + cred_id_bytes
            + cose_key_cbor
        )
        credential = AttestedCredentialData(credential_data)

        response = dict(data)
        resp_obj = dict(response.get("response") or {})

        try:
            resp_obj["clientDataJSON"] = b64url_decode(resp_obj["clientDataJSON"])
            resp_obj["authenticatorData"] = b64url_decode(resp_obj["authenticatorData"])
            resp_obj["signature"] = b64url_decode(resp_obj["signature"])
        except Exception:
            return jsonify({"result": "error", "message": "Invalid base64url in assertion response."}), 400

        if resp_obj.get("userHandle"):
            resp_obj["userHandle"] = b64url_decode(resp_obj["userHandle"])
        else:
            resp_obj["userHandle"] = None

        response["response"] = resp_obj

        server.authenticate_complete(
            state=state,
            credentials=[credential],
            response=response,
        )

        ad = AuthenticatorData(resp_obj["authenticatorData"])
        new_counter = ad.counter
        old_counter = pk.sign_count if pk.sign_count is not None else 0

        if new_counter == 0:
            pk.sign_count = old_counter
        else:
            if old_counter not in (None, 0) and new_counter <= old_counter:
                return jsonify({
                    "result": "error",
                    "message": "Potential cloned authenticator (signCount not increasing).",
                }), 400
            pk.sign_count = new_counter

        pk.save(db_session)

        user_sess = UserSession.by_id(get_jwt().get("id", None), db_session)
        if user_sess is None:
            return jsonify({"result": "error", "message": "Session not found"}), 404

        user_sess.passkey = True
        user_sess.partial = False
        user_sess.valid_passkey = True
        user_sess.sudo = True
        user_sess.save(db_session)

        access_jwt, refresh_jwt = user_sess.get_jwts(db_session)

        UserSession.clear_partial_sessions(user_obj.id, db_session)
        user_obj.fido2_state = None
        user_obj.fido2_state_timestamp = None
        user_obj.save(db_session)


        return jsonify({
            "result": "success",
            "message": {"access_jwt": access_jwt, "refresh_jwt": refresh_jwt},
            "user_obj": user_obj.to_dict(),
        }), 200
    finally:
        db_session.commit()
        db_session.close()


@bp.route("/delete", methods=["POST"])
def delete_passkey():
    data = request.json or {}
    if "id" not in data:
        return jsonify({"result": "error", "message": "PassKey id required"}), 400

    item = PassKey.by_id(data["id"])
    if not item:
        return jsonify({"result": "error", "message": "PassKey not found"}), 404
    if item.user_id != get_jwt_identity():
        return jsonify({"result": "error", "message": "PassKey not found"}), 404

    item.delete()

    return jsonify({"result": "success", "message": "Deleted", "deleted_id": data["id"]})