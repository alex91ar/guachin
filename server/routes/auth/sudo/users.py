from flask import request, jsonify, Blueprint
from models.user import User
from models.user_session import UserSession
from utils import check_password_complexity

bp = Blueprint("users", __name__, url_prefix="/users")


# ---------------- CREATE ---------------- #
@bp.route("/", methods=["POST"])
def create_user():
    """
    Create a new user.
    Expected JSON:
    {
        "id": "john_doe",
        "email": "john@example.com",
        "password": "StrongP@ss123",
        "roles": ["user"]
    }
    """
    data = request.get_json() or {}
    id = data.get("id")
    email = data.get("email")
    password = data.get("password")
    roles = data.get("roles", [])
    

    # ---------------- Validation ---------------- #
    if not all([id, email, password]):
        return jsonify({"result": "error", "message": "Missing required fields: id, email, password"}), 400

    if not isinstance(id, str) or not isinstance(email, str) or not isinstance(password, str):
        return jsonify({"result": "error", "message": "All fields must be strings"}), 422
    
    ok, errors = check_password_complexity(password)
    if not ok:
        return jsonify({
            "result": "error",
            "message": "Password not complex enough:\n" + "\n".join(errors)
        }), 400
    new_user = User.by_id(id)
    # ---------------- Duplicate Checks ---------------- #
    if new_user:
        return jsonify({"result": "error", "message": f"Username '{id}' already exists"}), 409
    else:
        new_user = User.by_email(email)
        if(new_user):
            return jsonify({"result": "error", "message": f"A user with email '{email}' already exists"}), 409
    # ---------------- Create User ---------------- #
    new_user = User(id=id, email=email)
    new_user.set_password(password)
    if roles and isinstance(roles, list):
        for r in roles:
            new_user.add_role(r)
    new_user.save()
    return jsonify({"result": "success", "message": new_user.to_dict()}), 201


# ---------------- READ ---------------- #
@bp.route("/", methods=["GET"])
def list_users():
    """List all users."""
    users = User.all()
    return jsonify({
        "result": "success",
        "message": [u.to_dict() for u in users]
    }), 200

# ---------------- UPDATE ---------------- #
@bp.route("/", methods=["PUT"])
def update_user():
    """
    Update user details.
    Expected JSON:
    {
        "id": "admin",
        "email": "new@example.com",
        "password": "NewStrongP@ss",
        "roles": ["vendor"]
    }
    """
    data = request.get_json() or {}

    username = data.get("id","")

    user = User.by_id(username)
    if not user:
        return jsonify({"result": "error", "message": "User not found"}), 404


    try:
        if "email" in data:
            user.email = data["email"]

        if "password" in data:
            user.password= data["password"]

        if "roles" in data and isinstance(data["roles"], list):
            user.clear_roles()
            for role in data["roles"]:
                user.add_role(role)
        user.prune_sessions()
        user.save()
        return jsonify({"result": "success", "message": user.to_dict()}), 200

    except ValueError as e:
        return jsonify({"result": "error", "message": str(e)}), 400
    except Exception as e:
        return jsonify({"result": "error", "message": str(e)}), 422

def change_password(user_obj, new_pw):
    try:
        user_obj.set_password(new_pw)   # ensure you have such a method
        user_obj.prune_sessions()
    except ValueError as e:
        return jsonify({"result":"error", "message":str(e)})
    return jsonify({"result":"ok", "message":"Password updated"})

@bp.route("/action", methods=["PUT"])
def do_user_action():
    """
    Do an action on an user.
    Expected JSON:
    {
        "id": "admin",
        "action": ""
    }
    """
    data = request.get_json() or {}

    username = data.get("id","")
    action = data.get("action","")
    value = data.get("value","")

    if not isinstance(username, str) or not isinstance(action, str):
        return jsonify({"result":"error", "message":"Invalid Input"}), 400 

    user_obj = User.by_id(username)
    if not user_obj:
        return jsonify({"result": "error", "message": "User not found"}), 404
    if action == "disable_twofa":
        return disable_user_2fa(user_obj)
    elif action == "delete":
        return delete_user(user_obj)
    elif action == "expire":
        return expire_user(value)
    elif action == "change_password":
        if not isinstance(value, str):
            return jsonify({"result":"error", "message":"Invalid Input"}), 400 
        return change_password(user_obj, value)
    else:
        return jsonify({"result":"error", "message":"Invalid action"}), 400


def disable_user_2fa(user_obj):
    """Disable a user's 2fa."""
    if not user_obj.twofa_enabled:
        return jsonify({"result":"error","message":f"{user_obj.id} doesn't have 2fa enabled."}),422
    user_obj.disable_2fa(token="",force=True)
    return jsonify({"result":"success","message":f"Disabled 2fa for user {user_obj.id}."}),202

def delete_user(user_obj):
    """Delete a user."""
    try:
        user_obj.delete()
        return jsonify({"result": "success", "message": f"User '{user_obj.id}' deleted successfully"}), 202
    except Exception as e:
        return jsonify({"result": "error", "message": str(e)}), 500

def expire_user(short_session_id):
    from routes.anon.auth import get_raw_token
    """Expire a user's sessions."""
    try:
        token_obj = UserSession.by_id(short_session_id)
        token_obj.valid_until = None
        token_obj.save()
        return jsonify({"result": "success", "message": f"Sessions for user '{user_obj.id}' expired."}), 202
    except Exception as e:
        return jsonify({"result": "error", "message": str(e)}), 500