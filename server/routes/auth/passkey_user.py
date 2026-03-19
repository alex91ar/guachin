from __future__ import annotations

import base64
import dataclasses
from datetime import datetime
from flask import Blueprint, request, jsonify, current_app
from fido2.webauthn import (
    PublicKeyCredentialRpEntity,
    PublicKeyCredentialUserEntity,
    PublicKeyCredentialDescriptor,
    AuthenticatorAttachment,
    UserVerificationRequirement,
)
import json
from models import User, UserSession
from models.passkey import PassKey
from flask_jwt_extended import get_jwt_identity, get_jwt
from webauthn.helpers.structs import PublicKeyCredentialRpEntity
from datetime import datetime
# --- add near the top with imports ---
from fido2.webauthn import AttestedCredentialData,AuthenticatorData 
from fido2.cose import CoseKey
from fido2.webauthn import (
    PublicKeyCredentialRpEntity,
    PublicKeyCredentialUserEntity,
    PublicKeyCredentialDescriptor,
    AuthenticatorAttachment,
    UserVerificationRequirement,
)
import struct
import cbor2 as cbor
from fido2.utils import websafe_decode as b64url_decode  # adjust to your import

def get_rp() -> PublicKeyCredentialRpEntity:
    domain = current_app.config["DOMAIN"]  # fail fast if missing
    return PublicKeyCredentialRpEntity(name=domain, id=domain)

def b64url_encode(b: bytes) -> str:
    """
    Encode bytes to base64url string without padding.
    """
    return base64.urlsafe_b64encode(b).rstrip(b'=').decode('ascii')


bp = Blueprint("passkeys", __name__, url_prefix="/passkeys")

def dict_to_base64(d):
    """Encode a dictionary into a base64 string."""
    json_str = json.dumps(d)
    b64_bytes = base64.b64encode(json_str.encode('utf-8'))
    return b64_bytes.decode('ascii')

def base64_to_dict(b64_str):
    """Decode a base64 string back into a dictionary."""
    json_bytes = base64.b64decode(b64_str)
    return json.loads(json_bytes.decode('utf-8'))

def get_fido2_server():
    return current_app.extensions["fido2_server"]

# ----------------------------
# Routes
# ----------------------------
@bp.route("/", methods=["GET"])
def list_passkeys():
    user = get_jwt_identity()

    keys = PassKey.all_by_user(user)
    return jsonify({
        "result": "success",
        "message": [
            {
                "id":k.id,
                "credential_id": k.credential_id,
                "sign_count": k.sign_count,
            }
            for k in keys
        ],
    })


@bp.route("/register/begin", methods=["POST"])
def register_begin():
    user_obj = None
    passkey_id = None
    try:
        server = get_fido2_server()
        username = get_jwt_identity()
        user_id = username.encode("utf-8")
        user_obj = User.by_id(username)
        if not user_obj:
            return jsonify({"result":"error","message":"Exception during registration begin."}), 500
        
        registration_data, state = server.register_begin(
            PublicKeyCredentialUserEntity(
                id=user_id,
                name=username,
                display_name=username
            ),
            [
            PublicKeyCredentialDescriptor(
                id=passkey.credential_id,
                type="public-key"
            ) for passkey in user_obj.passkeys
            ],
            user_verification=UserVerificationRequirement.PREFERRED,
            authenticator_attachment=AuthenticatorAttachment.PLATFORM,
        )
        print(registration_data)
        user_obj.fido2_state = dict_to_base64(state)
        user_obj.fido2_state_timestamp = datetime.utcnow()
        user_obj.save()
        return jsonify(jsonify_bytes(registration_data))
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        if(user_obj is not None):
            user_obj.fido2_state = None
            user_obj.fido2_state_timestamp = None
            user_obj.save()
        return jsonify({"result":"error","message":"Exception during registration begin " + type(e).__name__ + str(e)}), 500

def jsonify_bytes(obj):
    """Recursively convert bytes in dict/list structures to base64url strings."""
    if dataclasses.is_dataclass(obj):
        return jsonify_bytes(dataclasses.asdict(obj))
    elif isinstance(obj, dict):
        return {k: jsonify_bytes(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [jsonify_bytes(v) for v in obj]
    elif isinstance(obj, bytes):
        return base64.urlsafe_b64encode(obj).rstrip(b'=').decode('ascii')
    elif hasattr(obj, 'value'):
        return obj.value
    else:
        return obj

@bp.route("/register/complete", methods=["POST"])
def passkey_register_complete():
    """
    Expects the browser credential response payload.
    Stores PassKey(credential_id=base64url str, public_key bytes, sign_count int)
    """
    user = get_jwt_identity()
    data = request.get_json(force=True)
    user_obj = User.by_id(user)
    if not user_obj:
        return jsonify({"result":"error","message":"Exception during registration begin."}), 500
    server = get_fido2_server()

    try:
        state = base64_to_dict(user_obj.fido2_state)

        # Decode fields from base64url -> bytes for fido2
        response = data.copy()
        resp_obj = response["response"].copy()
        resp_obj["clientDataJSON"] = b64url_decode(resp_obj["clientDataJSON"])
        resp_obj["attestationObject"] = b64url_decode(resp_obj["attestationObject"])
        response["response"] = resp_obj

        auth_data = server.register_complete(state, response=response)

        cred_data = auth_data.credential_data
        credential_id_b64u = b64url_encode(cred_data.credential_id)

        # Persist
        pk = PassKey(
            user_id=user_obj.id,
            credential_id=credential_id_b64u,
            public_key=cbor.dumps(cred_data.public_key),
            credential_data=bytes(cred_data),   # ✅ store full ACD bytes
            sign_count=auth_data.counter or 0,
        )
        pk.save()

        return jsonify({"result": "success", "message": {"status": "ok"}})
    finally:
        if user_obj is not None:
            user_obj.fido2_state = None
            user_obj.fido2_state_timestamp = None
            user_obj.save()



@bp.route("/login/complete", methods=["POST"])
def passkey_login_complete():
    data = request.get_json(force=True) or {}
    username = (data.get("username") or "").strip()

    user_obj = User.by_id(username) if username else None
    if not user_obj or not user_obj.fido2_state:
        UserSession.clear_partial_sessions(username)
        return jsonify({"result": "error", "message": "Invalid or expired login attempt."}), 400

    server = get_fido2_server()

    try:
        state = base64_to_dict(user_obj.fido2_state)

        cred_id_b64u = (data.get("rawId") or data.get("id") or "").strip()
        if not cred_id_b64u:
            return jsonify({"result": "error", "message": "Missing credential id."}), 400

        pk = PassKey.by_credential_id(user_obj.id, cred_id_b64u)
        if not pk:
            return jsonify({"result": "error", "message": "Unknown passkey."}), 400

        cred_id_bytes = b64url_decode(cred_id_b64u)

        # ✅ Most DBs store pk.public_key as COSE_Key CBOR BYTES already.
        # If yours does, DO NOT cbor.loads()/dumps() it. Use directly:
        cose_key_bytes = pk.public_key

        # Optional sanity check (also “uses” the key)
        cose_key_cbor = pk.public_key                 # bytes (CBOR of COSE_Key)
        cose_key_map = cbor.loads(cose_key_cbor)      # dict-like
        _public_key = CoseKey.parse(cose_key_map)     # ✅ now works

        # AAGUID handling
        aaguid = getattr(pk, "aaguid", None)
        if aaguid:
            aaguid_bytes = aaguid if isinstance(aaguid, (bytes, bytearray)) else bytes.fromhex(aaguid)
            aaguid_bytes = aaguid_bytes[:16].ljust(16, b"\x00")
        else:
            aaguid_bytes = b"\x00" * 16

        # ✅ AttestedCredentialData = aaguid(16) + credIdLen(2) + credId + coseKey(CBOR bytes)
        credential_data = (
            aaguid_bytes
            + struct.pack(">H", len(cred_id_bytes))
            + cred_id_bytes
            + cose_key_cbor
        )
        credential = AttestedCredentialData(credential_data)

        # Normalize assertion response to bytes
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

        # Verify signature + rpIdHash + challenge, etc.
        server.authenticate_complete(
            state=state,
            credentials=[credential],
            response=response,
        )

        # ✅ Use the signCount from authenticatorData (reliable)
        ad = AuthenticatorData(resp_obj["authenticatorData"])
        new_counter = ad.counter  # int

        # ✅ Enforce monotonic counter (FIDO2 guidance: 0 may mean “not supported”)
        old_counter = pk.sign_count if pk.sign_count is not None else 0

        # If authenticator reports 0, many authenticators mean "counter not supported"
        # In that case, don't enforce and don't “decrease” stored value.
        if new_counter == 0:
            # keep existing stored value (or set to 0 if empty)
            pk.sign_count = old_counter
        else:
            # If we have a previous non-zero counter, require increase
            if old_counter not in (None, 0) and new_counter <= old_counter:
                return jsonify({
                    "result": "error",
                    "message": "Potential cloned authenticator (signCount not increasing)."
                }), 400
            pk.sign_count = new_counter

        pk.save()

        user_sess = UserSession.by_id(get_jwt().get("id", None))
        user_sess.passkey = True
        user_sess.save()

        access_jwt, refresh_jwt = user_sess.get_jwts()
        return jsonify({
            "result": "success",
            "message": {"access_jwt": access_jwt, "refresh_jwt": refresh_jwt},
            "user_obj": user_obj.to_dict(),
        }), 200

    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return jsonify({"result": "error", "message": f"Exception during login complete: {type(e).__name__} {e}"}), 400

    finally:
        UserSession.clear_partial_sessions(username)
        user_obj.fido2_state = None
        user_obj.fido2_state_timestamp = None
        user_obj.save()


@bp.route("/delete", methods=["POST"])
def delete_passkey():
    data = request.json or {}
    if "id" not in data:
        return jsonify({"result": "error", "message": "PassKey id required"}), 400

    item = PassKey.query.get(data["id"])
    if not item:
        return jsonify({"result": "error", "message": "PassKey not found"}), 404
    if item.user_id != get_jwt_identity():
        return jsonify({"result": "error", "message": "PassKey not found"}), 404
    item.delete()

    return jsonify({"result": "success", "message": "Deleted", "deleted_id": data["id"]})
