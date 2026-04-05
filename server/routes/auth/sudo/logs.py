from flask import Blueprint, jsonify

from models.log import Log

bp = Blueprint("logs", __name__, url_prefix="/logs")


@bp.route("/", methods=["GET"])
def get_all_logs():
    logs = Log.all()
    return jsonify({
        "result": "success",
        "message": [log.to_dict() for log in logs],
    }), 200


@bp.route("/purge", methods=["GET"])
def purge_all_logs():
    Log.clear_table()
    return jsonify({
        "result": "success",
        "message": "All logs purged.",
    }), 200