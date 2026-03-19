from flask_admin import Admin
from flask_admin.contrib.fileadmin import FileAdmin
from flask import redirect, url_for, request, abort
from flask_jwt_extended import get_jwt
from routes.anon.auth import get_raw_token
from utils import gen_key
from flask_jwt_extended import decode_token
from flask_jwt_extended.exceptions import JWTExtendedException
from flask_admin.theme import Bootstrap4Theme
import json

FILE_MANAGER_KEY = gen_key("/admin/fileadmin", "GET")

def is_jwt_valid(encoded_jwt: str) -> bool:
    if not encoded_jwt:
        return False
    try:
        _claims = decode_token(encoded_jwt)  # validates sig + exp, etc.
        return _claims
    except JWTExtendedException:
        return False
    except Exception:
        # anything unexpected (bad formatting, etc.)
        return False

# example: plug in your own auth logic
def is_current_user_admin() -> bool:
    auth_cookie = request.cookies.get("jwt_cookie", None)
    claims = is_jwt_valid(auth_cookie)
    if claims == False:
        return False
    if "file_manager" not in claims.get("perms",None):
        return False
    return True

class AdminOnlyFileAdmin(FileAdmin):
    def is_accessible(self):
        return is_current_user_admin()

    def inaccessible_callback(self, name, **kwargs):
        # either redirect to login or just 403
        return abort(403)

def init_admin(app):
    admin = Admin(app, name="Admin", theme=Bootstrap4Theme())

    # IMPORTANT: pick a safe directory; do NOT point at your project root
    uploads_root = app.config["UPLOAD_ROOT"]  # e.g. /var/app/uploads

    admin.add_view(AdminOnlyFileAdmin(
        uploads_root,
        name="File Manager",
        endpoint="fileadmin",
        
        # optional: if you also serve files publicly from a URL prefix
        # base_url="/static/uploads/"
    ))
    return admin
