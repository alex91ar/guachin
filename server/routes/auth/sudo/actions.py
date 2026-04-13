from flask import Blueprint, current_app, jsonify

from models.action import Action
from models.schema import populate_actions_from_routes
from utils import generate_urls

bp = Blueprint("actions", __name__, url_prefix="/actions")


@bp.route("/reset", methods=["GET"])
def reset_actions():
    Action.clear_table()

    ok = populate_actions_from_routes(current_app)
    if not ok:
        return jsonify({
            "result": "error",
            "message": "Failed to repopulate actions.",
        }), 500

    generate_urls(current_app)

    return jsonify({
        "result": "success",
        "message": "Actions reset.",
    }), 200