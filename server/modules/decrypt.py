NAME = "decrypt"
DESCRIPTION = "Decrypt a file using the server's key."
PARAMS = [
    {"name":"file", "description":"Decrypt a file on the client using the server's key.", "type":"str"}
]

# Dependencies: 
# 1. NtQueryInformationProcess (to find PEB)
DEPENDENCIES = ["read", "write", "isencrypted"]
DEFAULT = True

def generate_server_key():
    from hashlib import pbkdf2_hmac
    from flask import current_app
    password = current_app
    salt = current_app.config["SECRET_KEY"][:16]
    iterations = 2000
    return pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations, dklen=32)

def decrypt_blob(blob: bytes, header_len: int) -> tuple[bytes, bytearray]:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from hashlib import pbkdf2_hmac
    from flask import current_app

    secret = current_app.config["SECRET_KEY"]

    header = blob[:header_len]
    salt_start = header_len
    nonce_start = salt_start + 16
    ciphertext_start = nonce_start + 12

    salt = blob[salt_start:nonce_start]
    nonce = blob[nonce_start:ciphertext_start]
    ciphertext = blob[ciphertext_start:]

    key = pbkdf2_hmac("sha256", secret.encode("utf-8"), salt, 2000, dklen=32)
    aesgcm = AESGCM(key)
    plaintext = aesgcm.decrypt(nonce, ciphertext, None)

    return bytes(plaintext)


def function(agent_id, args):
    file = args[0]
    ret = isencrypted(agent_id, [file])
    if ret["retval"] != 0:
        {"retval":-1, "message":"Error opening file"}
    if ret["encrypted"] == "0":
        return {"retval":-1, "message":"File not encrypted"}
    data = read(agent_id, [file])
    if(data["retval"] != 0):
        return {"retval":-1,"message":"Error opening file"}
    data = data["data"]
    decrypted = decrypt_blob(data, 8)
    write_ret = write(agent_id, [file, decrypted])
    if write_ret["retval"] != 0:
        return {"retval":-1, "message":"Error writing"}
    return {"retval":0} 

