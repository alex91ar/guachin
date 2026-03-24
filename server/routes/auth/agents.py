from flask import request, jsonify, Blueprint, url_for

from models import db, Agent
from flask_jwt_extended import get_jwt_identity
from routes.auth.sudo.system import verify_tokens
from app import auth_bp
from models.line import Line
import logging
logger = logging.getLogger(__name__)
from routes.auth.sudo.system import sock
from services.agent_ws import _shell_ws_agent

bp = Blueprint("agent", __name__, url_prefix="/agent")


@sock.route(f"{auth_bp.url_prefix}{bp.url_prefix}/ws/<agent_id>")
def agent_ws(ws, agent_id):
    print("Connecting agent...")
    # ---- handshake (unchanged) ----
    try:
        msg = ws.receive(timeout=5)
    except Exception:
        logger.info("No handshake received.")
        ws.send("[auth] no handshake received\n")
        ws.close()
        return

    ok, err, identity = verify_tokens(msg or "")
    if not ok:
        logger.info("Auth Failed.")
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


# ---------------- READ ---------------- #
@bp.route("/", methods=["GET"])
def list_agents():
    """List all agents."""
    try:
        id = get_jwt_identity()
        agents = Agent.by_user_name(id)

        return jsonify({
            "result": "success",
            "message": [agent.to_dict() for agent in agents]
        }), 200
    except Exception as e:
        return jsonify({
            "result": "error",
            "message": str(e)
        }), 500


# ---------------- DELETE ---------------- #
@bp.route("/delete", methods=["POST"])
def delete_agent():
    """
    Delete an agent.
    Expected JSON:
    {
        "id": 1
    }
    """
    data = request.get_json() or {}
    agent_id = data.get("id")

    if agent_id is None:
        return jsonify({
            "result": "error",
            "message": "Missing required field: id"
        }), 400

    try:
        agent_id = int(agent_id)
    except (TypeError, ValueError):
        return jsonify({
            "result": "error",
            "message": "id must be an integer"
        }), 422

    agent = Agent.by_id(agent_id)
    user_id = get_jwt_identity()
    if not agent or agent.user_id != user_id:
        return jsonify({
            "result": "error",
            "message": "Agent not found"
        }), 404

    try:
        agent.delete()
        return jsonify({
            "result": "success",
            "message": f"Agent '{agent_id}' deleted successfully"
        }), 202
    except Exception as e:
        return jsonify({
            "result": "error",
            "message": str(e)
        }), 500
    
# ---------------- INTERACT ---------------- #
@bp.route("/interact", methods=["POST"])
def get_agent():
    """
    Get an agent interaction websocket route.
    Expected JSON:
    {
        "id": 1
    }
    """
    data = request.get_json() or {}
    agent_id = data.get("id")

    if agent_id is None:
        return jsonify({
            "result": "error",
            "message": "Missing required field: id"
        }), 400

    user_id = get_jwt_identity()
    agent = Agent.by_id(agent_id)

    if not agent or agent.user_id != user_id:
        return jsonify({
            "result": "error",
            "message": "Agent not found"
        }), 404

    websocket_url = f"{auth_bp.url_prefix}{bp.url_prefix}/ws/{agent.id}"

    return jsonify({
        "result": "success",
        "message": {
            "agent": agent.to_dict(),
            "websocket_url": websocket_url
        }
    }), 200
