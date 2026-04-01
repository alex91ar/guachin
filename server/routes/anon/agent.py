from flask import request, jsonify, Blueprint, current_app, g, url_for
from app import anon_bp
from flask_jwt_extended.exceptions import JWTExtendedException
from routes.auth.sudo.system import sock
from models.agent import Agent
from models.request import Request
from models.syscall import Syscall
import logging
import struct
logger = logging.getLogger(__name__)

bp = Blueprint("agent", __name__, url_prefix='/agent')

from flask import request, current_app
import threading
import time

def split_three(data: bytes | bytearray):
    first = data[:8]
    second = data[8:16]
    rest = data[16:]
    return first, second, rest

def parse_handshake(msg, agent_id):
    os_bytes, scratchpad, syscall_blob = split_three(msg)
    db_session, agent = Agent.by_id_lock(agent_id)
    agent.os = struct.unpack("<Q",os_bytes)[0]
    agent.scratchpad = struct.unpack("<Q",scratchpad)[0]
    print(f"New agent os = {hex(struct.unpack("<Q",os_bytes)[0])} {len(os_bytes)}, scratchpad = {hex(struct.unpack("<Q",scratchpad)[0])}")
    Syscall.save_syscalls_bytes(agent.id, syscall_blob, db_session)
    db_session.commit()
    db_session.remove()

def handle_msg_type(request_id):
    request_obj = None
    while True:
        db_session, request_obj = Request.by_id_lock(request_id)
        if request_obj is None:
            break
        if request_obj.response != None:
            break
        db_session.remove()
    msg = request_obj.response
    msg_type = msg[0]
    payload = msg[1:]

    if msg_type == 0x00:
        # handshake
        parse_handshake(payload, request_obj.agent_id)
    elif msg_type == 0x01:
        return payload
    else:
        print(f"Unknown message type {msg_type}")

def create_handshake(agent_id):
    to_send = bytearray()
    to_send.extend(b'\x00')
    request_obj = Request(agent_id, to_send)
    handle_msg_type(request_obj.id)

@sock.route(f"{anon_bp.url_prefix}{bp.url_prefix}/ws/<agent_id>")
def server_agent_ws(ws, agent_id):
    import threading
    import time

    from flask import current_app
    from models.agent import Agent
    from models.request import Request
    from models.db import get_session

    print(f"Starting websocket for agent {agent_id}...")

    agent = Agent.by_id(agent_id)
    if agent is None:
        agent = Agent(agent_id, "admin")
        agent.save()

    app = current_app._get_current_object()
    stop_event = threading.Event()
    last_request_id = None

    def normalize_to_bytes(data):
        if isinstance(data, str):
            return data.encode("utf-8")
        if isinstance(data, bytearray):
            return bytes(data)
        return data

    def mark_request_sent(request_id):
        db_session, req = Request.by_id_lock(request_id)

        req.sent = True
        db_session.commit()
        db_session.remove()
        return True

    def save_request_response(request_id, message):
        db_session, req = Request.by_id_lock(request_id)

        req.response = message
        db_session.commit()
        db_session.remove()
        return True

    def poll_requests():
        nonlocal last_request_id

        with app.app_context():
            while not stop_event.is_set():
                try:
                    request_obj = Request.by_agent(agent_id)

                    if request_obj is None:
                        continue

                    request_id = request_obj.id

                    if last_request_id == request_id:
                        continue

                    if request_obj.sent is True:
                        continue

                    data = normalize_to_bytes(request_obj.content)
                    if not isinstance(data, bytes) or not data:
                        continue


                    try:
                        ws.send(data)
                        last_request_id = request_id
                        

                        if not mark_request_sent(request_id):
                            stop_event.set()
                            break

                    except Exception:
                        logger.exception(
                            "Failed sending request %s to agent %s",
                            request_id,
                            agent_id,
                        )
                        stop_event.set()
                        break


                except Exception:
                    logger.exception("Polling request failed for agent %s", agent_id)
                    stop_event.set()

    threading.Thread(target=poll_requests, daemon=True).start()
    threading.Thread(target=create_handshake, args=(agent_id,), daemon=True).start()

    try:
        while not stop_event.is_set():
            try:
                message = ws.receive()
            except Exception:
                logger.info("WebSocket receive failed/closed for agent %s", agent.id)
                break

            if message is None:
                logger.info("WebSocket closed for agent %s", agent.id)
                break

            message = normalize_to_bytes(message)

            if not isinstance(message, bytes) or not message:
                continue


            current_request_id = last_request_id
            if current_request_id is None:
                logger.warning("Received response from agent %s but no pending request id", agent_id)
                continue

            with app.app_context():
                save_request_response(current_request_id, message)

    finally:
        print(f"Closing websocket with agent {agent_id}")
        stop_event.set()
        if agent is not None:
            try:
                print(f"Setting {agent_id} as offline")
                Agent.to_offline(agent_id)
            except Exception:
                logger.exception("Failed updating agent %s offline state", agent_id)

        try:
            ws.close()
        except Exception:
            pass