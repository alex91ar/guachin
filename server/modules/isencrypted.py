NAME = "isencrypted"
DESCRIPTION = "Checks whether a file is encrypted."
PARAMS = [
    {"name":"file", "description":"File to encrypt.", "type":"str"}
]

DEPENDENCIES = ["read"]
DEFAULT = True

def generate_encrypted_header():
    from flask import current_app
    from hashlib import pbkdf2_hmac
    secret = current_app.config["SECRET_KEY"].encode()
    salt = current_app.config["SECRET_KEY"][:16].encode()
    iterations = 200
    header = pbkdf2_hmac("sha256", secret, salt, iterations, dklen=32)[:8]
    return header

def is_encrypted(data, header):
    if len(data) > 8 and data[:8] == header:
        return True
    return False


def function(agent_id, args):
    filename = args[0]
    ret = read(agent_id, [filename])
    if ret["retval"] !=0:
        return {"retval":-1, "message":"Error reading file"}
    data = ret["data"]
    header = generate_encrypted_header()
    if is_encrypted(data, header):
        return {"retval":0, "encrypted":"1"}
    else:
        return {"retval":0, "encrypted":"0"}