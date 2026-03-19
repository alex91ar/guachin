from flask import jsonify, Blueprint, current_app
from models.action import Action
from models.basemodel import db
from models.schema import populate_actions_from_routes
from utils import generate_urls

bp = Blueprint("actions", __name__, url_prefix='/actions')


# ---------------- READ ---------------- #
@bp.route("/", methods=["GET"])
def list_actions():
    """
    List all actions.
    """
    actions = Action.all()
    return jsonify({"result":"success","message":[r.to_dict() for r in actions]}), 200


@bp.route("/reset", methods=["GET"])
def reset_actions():
    from models.db import engine
    """
    Reload all actions and basic roles
    """
    actions = Action.all()
    for i in range(len(actions) - 1, -1, -1):
        actions[i].delete()
    populate_actions_from_routes(current_app)
    generate_urls(current_app)
    return jsonify({"result":"success", "message":"Actions resetted."}), 200

