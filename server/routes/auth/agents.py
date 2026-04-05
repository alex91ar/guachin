from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity

from models.agent import Agent
from routes.auth.sudo.system import sock, verify_tokens
from services.agent_ws import _shell_ws_agent

import logging

logger = logging.getLogger(__name__)

bp = Blueprint("agent", __name__, url_prefix="/agent")


@sock.route(f"/api/v1/auth{bp.url_prefix}/ws/<agent_id>")
def agent_ws(ws, agent_id):
    print("Connecting agent...")

    try:
        msg = ws.receive(timeout=5)
    except Exception:
        logger.info("No handshake received.")
        ws.send("[auth] no handshake received\n")
        ws.close()
        return

    parent_path = request.path.rsplit("/", 1)[0] + "/"
    ok, err, identity = verify_tokens(msg, parent_path)
    if not ok:
        logger.info("Auth failed.")
        ws.send(f"[auth] failed: {err}\n")
        ws.close()
        return

    agent = Agent.by_id(agent_id)
    if not agent or agent.user_id != identity:
        logger.info("Agent not found.")
        ws.send(f"[auth] failed: {err}\n")
        ws.close()
        return

    return _shell_ws_agent(ws, agent, identity)


@bp.route("/", methods=["GET"])
def list_agents():
    user_id = get_jwt_identity()
    agents = Agent.all_by_user(user_id)

    return jsonify({
        "result": "success",
        "message": [agent.to_dict() for agent in agents],
    }), 200


@bp.route("/delete", methods=["POST"])
def delete_agent():
    data = request.get_json() or {}
    agent_id = data.get("id")

    if agent_id is None:
        return jsonify({
            "result": "error",
            "message": "Missing required field: id",
        }), 400

    agent = Agent.by_id(agent_id)
    user_id = get_jwt_identity()

    if not agent or agent.user_id != user_id:
        return jsonify({
            "result": "error",
            "message": "Agent not found",
        }), 404

    agent.delete()

    return jsonify({
        "result": "success",
        "message": f"Agent '{agent_id}' deleted successfully",
    }), 202


@bp.route("/interact", methods=["POST"])
def get_agent():
    data = request.get_json() or {}
    agent_id = data.get("id")

    if agent_id is None:
        return jsonify({
            "result": "error",
            "message": "Missing required field: id",
        }), 400

    user_id = get_jwt_identity()
    agent = Agent.by_id(agent_id)

    if not agent or agent.user_id != user_id:
        return jsonify({
            "result": "error",
            "message": "Agent not found",
        }), 404

    websocket_url = f"/api/v1/auth{bp.url_prefix}/ws/{agent.id}"

    return jsonify({
        "result": "success",
        "message": {
            "agent": agent.to_dict(),
            "websocket_url": websocket_url,
        },
    }), 200