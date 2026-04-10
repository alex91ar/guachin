# routes/auth/sudo/system.py
from __future__ import annotations

import json
import logging
import os
import platform
import signal
import socket
import threading
import time
from datetime import timedelta
from typing import Optional, Tuple

import psutil
from flask import Blueprint, current_app, jsonify, make_response, redirect, request, url_for
from flask_jwt_extended import create_access_token, decode_token
from routes.anon.auth import get_token_manually
from flask_jwt_extended.exceptions import JWTExtendedException
from flask_sock import Sock
from flask_wtf.csrf import validate_csrf
from simple_websocket.errors import ConnectionClosed

from utils import gen_key

bp = Blueprint("system", __name__, url_prefix="/system")
sock = Sock()
boot_time = psutil.boot_time()
logger = logging.getLogger(__name__)

_active_shells_lock = threading.Lock()
_active_shells: dict[str, dict[str, object]] = {}


@bp.record_once
def init_sock(state):
    sock.init_app(state.app)


def verify_tokens(msg: str, path) -> Tuple[bool, Optional[str], Optional[str]]:
    try:
        data = json.loads(msg)
    except Exception:
        return False, "invalid_json", None

    if data.get("type") != "auth":
        return False, "invalid_handshake_type", None

    jwt_token = data.get("access_jwt")
    csrf_token = data.get("csrf_token")
    if not jwt_token or not csrf_token:
        return False, "missing_tokens", None

    try:
        claims = decode_token(jwt_token)
    except JWTExtendedException as e:
        return False, f"jwt_error:{e}", None
    except Exception as e:
        return False, f"decode_error:{e}", None

    if claims.get("sudo") is not True:
        return False, "sudo_required", None

    try:
        validate_csrf(csrf_token, secret_key=current_app.config["SECRET_KEY"])
    except Exception:
        return False, "invalid_csrf_token", None

    method = request.method
    key = gen_key(path, method)
    if key not in (claims.get("perms") or []):
        return False, "permission_not_granted", None

    identity = claims.get("sub")
    logger.critical("Shell authenticated.")
    return True, None, identity


def _terminate_previous_shell(identity: str):
    with _active_shells_lock:
        prev = _active_shells.pop(identity, None)

    if not prev:
        return

    try:
        if os.name == "nt":
            import subprocess

            subprocess.run(
                ["taskkill", "/PID", str(prev["pid"]), "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
        else:
            pgrp = prev.get("pgrp")
            if pgrp:
                os.killpg(int(pgrp), signal.SIGTERM)
            else:
                os.kill(int(prev["pid"]), signal.SIGTERM)
    except Exception:
        pass


def _shell_ws_windows_pty(ws, identity):
    import shutil

    from winpty import PtyProcess

    logger.info("Starting windows shell...")
    shell = "powershell.exe" if shutil.which("powershell") else "cmd.exe"

    pty = PtyProcess.spawn(
        shell,
        cwd=os.getcwd(),
        env=os.environ.copy(),
    )
    pid = pty.pid

    with _active_shells_lock:
        _active_shells[identity] = {"os": "nt", "pid": pid, "pgrp": None}

    cmd_buffer = ""

    def pty_to_ws():
        try:
            while pty.isalive():
                try:
                    data = pty.read(4096)
                    if data:
                        ws.send(data)
                except Exception:
                    time.sleep(0.02)
        finally:
            try:
                ws.close()
            except Exception:
                pass

    threading.Thread(target=pty_to_ws, daemon=True).start()

    try:
        while True:
            incoming = ws.receive()
            if incoming is None:
                break

            if isinstance(incoming, str) and incoming.startswith("__resize__"):
                try:
                    _, cols, rows = incoming.split(":", 2)
                    pty.set_size(int(rows), int(cols))
                except Exception:
                    pass
                continue

            if isinstance(incoming, str):
                cmd_buffer += incoming
                if incoming.endswith("\n") or incoming.endswith("\r"):
                    clean = cmd_buffer.strip()
                    if clean:
                        logger.critical("Shell command: %s", clean)
                    cmd_buffer = ""
                pty.write(incoming)
    finally:
        with _active_shells_lock:
            cur = _active_shells.get(identity)
            if cur and cur.get("pid") == pid:
                _active_shells.pop(identity, None)

        try:
            pty.close()
        except Exception:
            pass


def _shell_ws_unix_pty(ws, identity):
    import fcntl
    import pty
    import select
    import struct
    import termios

    logger.info("Starting unix shell...")
    shell = "/bin/bash" if os.path.exists("/bin/bash") else "/bin/sh"
    cmd_buffer = ""

    pid, fd = pty.fork()
    if pid == 0:
        os.environ["TERM"] = os.environ.get("TERM", "xterm-256color")
        os.execvp(shell, [shell, "-i"])

    pgrp = os.getpgid(pid)

    with _active_shells_lock:
        _active_shells[identity] = {"os": "posix", "pid": pid, "pgrp": pgrp}

    flags = fcntl.fcntl(fd, fcntl.F_GETFL)
    fcntl.fcntl(fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)

    stop_event = threading.Event()

    def pty_to_ws():
        try:
            while not stop_event.is_set():
                try:
                    r, _, _ = select.select([fd], [], [], 0.05)
                except OSError as e:
                    if getattr(e, "errno", None) == 9:
                        break
                    raise

                if fd in r:
                    try:
                        data = os.read(fd, 4096)
                        if not data:
                            break
                        try:
                            ws.send(data.decode(errors="ignore"))
                        except ConnectionClosed:
                            break
                        except Exception:
                            break
                    except OSError as e:
                        if getattr(e, "errno", None) in (5, 9):
                            break
                        break
        except Exception as e:
            logger.exception("Exception reading from PTY: %s", e)
        finally:
            stop_event.set()
            try:
                ws.close()
            except Exception:
                pass

    t = threading.Thread(target=pty_to_ws, daemon=True)
    t.start()

    try:
        while not stop_event.is_set():
            try:
                incoming = ws.receive()
            except ConnectionClosed:
                break

            if incoming is None:
                break

            if isinstance(incoming, str) and incoming.startswith("__resize__"):
                try:
                    _, cols, rows = incoming.split(":", 2)
                    cols_i, rows_i = int(cols), int(rows)
                    fcntl.ioctl(
                        fd,
                        termios.TIOCSWINSZ,
                        struct.pack("HHHH", rows_i, cols_i, 0, 0),
                    )
                except Exception:
                    pass
                continue

            if isinstance(incoming, str):
                cmd_buffer += incoming
                if incoming.endswith("\n") or incoming.endswith("\r"):
                    clean = cmd_buffer.strip()
                    if clean:
                        logger.critical("Shell command: %s", clean)
                    cmd_buffer = ""

                try:
                    os.write(fd, incoming.encode())
                except OSError:
                    break
    except Exception as e:
        logger.exception("Exception on shell loop: %s", e)
    finally:
        stop_event.set()

        with _active_shells_lock:
            cur = _active_shells.get(identity)
            if cur and cur.get("pid") == pid:
                _active_shells.pop(identity, None)

        try:
            os.kill(pid, signal.SIGHUP)
        except Exception:
            pass

        try:
            t.join(timeout=0.5)
        except Exception:
            pass

        try:
            os.close(fd)
        except Exception:
            pass


@sock.route("/api/v1/auth/sudo/system/shell/ws")
def shell_ws(ws):
    logger.info("Starting shell...")
    try:
        msg = ws.receive(timeout=5)
    except Exception:
        logger.info("No handshake received.")
        ws.send("[auth] no handshake received\n")
        ws.close()
        return

    ok, err, identity = verify_tokens(msg, request.path)
    if not ok:
        logger.info("Auth failed: %s", err)
        ws.send(f"[auth] failed: {err}\n")
        ws.close()
        return

    _terminate_previous_shell(identity)

    if os.name == "nt":
        return _shell_ws_windows_pty(ws, identity)
    return _shell_ws_unix_pty(ws, identity)


@bp.route("/jwt-to-cookie", methods=["GET"])
def jwt_to_cookie():
    identity, _ = get_token_manually()

    resp = jsonify({"result": "ok"})
    resp.set_cookie(
        "jwt_cookie",
        identity,
        max_age=60 * 60,
        httponly=True,
        samesite="Lax",
        secure=True,
        path="/",
    )
    return resp


@bp.route("/info", methods=["GET"])
def get_system_info():
    try:
        uptime_sec = int(time.time() - boot_time)
        uptime_hours = uptime_sec // 3600

        load_avg = os.getloadavg() if hasattr(os, "getloadavg") else (0.0, 0.0, 0.0)
        mem = psutil.virtual_memory()

        info = {
            "hostname": socket.gethostname(),
            "platform": f"{platform.system()} {platform.release()}",
            "python": platform.python_version(),
            "uptime": f"{uptime_hours}h",
            "cpu": f"{psutil.cpu_percent(interval=0.5)}%",
            "load": f"{load_avg[0]:.2f}, {load_avg[1]:.2f}, {load_avg[2]:.2f}",
            "mem": f"{mem.percent}%",
        }
        return jsonify(info), 200
    except Exception as e:
        logger.exception("Failed to gather system info: %s", e)
        return jsonify({"error": str(e)}), 500