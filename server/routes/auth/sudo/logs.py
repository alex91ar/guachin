from flask import render_template, request, redirect, url_for, flash, Blueprint, jsonify
from flask_jwt_extended import jwt_required, get_jwt, get_jwt_identity, JWTManager
from models.log import Log
bp = Blueprint("logs", __name__,url_prefix='/logs')

@bp.route("/", methods=["GET"])
def get_all_logs():
    return jsonify({"result":"success","message":[r.to_dict() for r in Log.all()]}), 200

@bp.route("/purge", methods=["GET"])
def purge_all_logs():
    return jsonify({"result":"success","message":[r.delete() for r in Log.all()]}), 200
 