from flask_admin import Admin
from flask_admin.contrib.fileadmin import FileAdmin
from flask_admin.theme import Bootstrap4Theme
from flask import abort, request
from flask_jwt_extended import decode_token
from flask_jwt_extended.exceptions import JWTExtendedException
from utils import gen_key

FILE_MANAGER_KEY = gen_key("/admin/files/", "GET")


def is_current_user_admin() -> bool:
    from routes.anon.auth import get_token_claims_manually
    from models.user_session import UserSession
    auth_cookie = request.cookies.get("jwt_cookie")
    claims, _ = get_token_claims_manually(auth_cookie)
    if not claims:
        return False
    id = claims.get("id", None)
    session = UserSession.by_id(id)
    if session is not None and session.is_valid():
        perms = claims.get("perms") or []
        return FILE_MANAGER_KEY in perms
    else:
        return False


class AdminOnlyFileAdmin(FileAdmin):
    extra_css = ["/static/css/flask_admin_dark.css"]
    def is_accessible(self):
        ret = is_current_user_admin()
        if not ret:
            abort(403)
        return ret

    def inaccessible_callback(self, name, **kwargs):
        return abort(403)


def init_admin(app):
    
    uploads_root = app.config["UPLOAD_ROOT"]

    admin = Admin(
        app,
        name="File Admin",
        theme=Bootstrap4Theme()
    )

    admin.add_view(
        AdminOnlyFileAdmin(
            uploads_root,
            name="File Manager",
            endpoint="files",
        )
    )
    return admin