# routes/auth/sudo/system.py
from __future__ import annotations

import json
import logging
import os
import platform
import socket
import threading
import time
from typing import Tuple, Optional
from flask_jwt_extended import create_access_token,create_refresh_token, jwt_required, get_jwt_identity, get_jwt
from datetime import timedelta
import psutil
from routes.anon.auth import get_raw_token
from flask import Blueprint, jsonify, current_app, request, make_response, redirect, url_for
from flask_sock import Sock
from flask_wtf.csrf import validate_csrf
from flask_jwt_extended import decode_token
from flask_jwt_extended.exceptions import JWTExtendedException
import signal
from utils import gen_key
from app import sudo_bp
from simple_websocket.errors import ConnectionClosed

bp = Blueprint("system", __name__, url_prefix="/system")
sock = Sock()
boot_time = psutil.boot_time()
logger = logging.getLogger(__name__)

_active_shells_lock = threading.Lock()
_active_shells = {}  # key -> {"os":"nt|posix", "pid": int, "pgrp": int|None
@bp.record_once
def init_sock(state):
    sock.init_app(state.app)


# ---------------------------
# Auth helpers
# ---------------------------

def verify_tokens(msg: str) -> Tuple[bool, Optional[str]]:
    """Verify JWT + CSRF tokens from WS handshake message."""
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

    path = request.url_rule.rule
    method = request.method
    key = gen_key(path, method)
    if key not in (claims.get("perms") or []):
        return False, "permission_not_granted", None
    identity = claims.get("sub")  # flask-jwt-extended stores identity in "sub"
    logger.critical("Shell authenticated.")
    return True, None, identity

def _terminate_previous_shell(identity: str):
    """Kill previously spawned shell for this identity (if any)."""
    with _active_shells_lock:
        prev = _active_shells.pop(identity, None)

    if not prev:
        return

    try:
        if os.name == "nt":
            # On Windows, kill the process tree safely.
            # Requires pid
            import subprocess
            subprocess.run(
                ["taskkill", "/PID", str(prev["pid"]), "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
        else:
            # On Unix, kill the whole process group (best practice for PTYs).
            pgrp = prev.get("pgrp")
            if pgrp:
                os.killpg(pgrp, signal.SIGTERM)
            else:
                os.kill(prev["pid"], signal.SIGTERM)
    except Exception:
        pass


def _shell_ws_windows_pty(ws, identity):
    print("Starting windows shell...")
    import threading
    from winpty import PtyProcess
    import time
    import shutil

    # Prefer PowerShell, fallback to cmd
    shell = "powershell.exe" if shutil.which("powershell") else "cmd.exe"

    pty = PtyProcess.spawn(
        shell,
        cwd=os.getcwd(),
        env=os.environ.copy(),
    )
    pid = pty.pid  # ✅ available in pywinpty

    with _active_shells_lock:
        _active_shells[identity] = {"os": "nt", "pid": pid, "pgrp": None}
    cmd_buffer = ""

    # ---- PTY -> WS ----
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

    # ---- WS -> PTY ----
    try:
        while True:
            incoming = ws.receive()
            if incoming is None:
                break

            # Resize protocol: "__resize__:cols:rows"
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
    print("Starting unix shell...")
    import pty
    import fcntl
    import termios
    import struct
    import select
    import signal
    import threading
    import os

    from simple_websocket.errors import ConnectionClosed

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

    # ---- PTY -> WS thread ----
    def pty_to_ws():
        try:
            while not stop_event.is_set():
                try:
                    r, _, _ = select.select([fd], [], [], 0.05)
                except OSError as e:
                    # fd closed (EBADF) during shutdown => normal
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
                        # fd closed / child exited => normal
                        if getattr(e, "errno", None) in (5, 9):  # EIO, EBADF
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

    # ---- WS -> PTY main loop ----
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

        # Try to stop child first
        try:
            os.kill(pid, signal.SIGHUP)
        except Exception:
            pass

        # Let reader thread exit before closing fd to avoid EBADF spam
        try:
            t.join(timeout=0.5)
        except Exception:
            pass

        try:
            os.close(fd)
        except Exception:
            pass


@sock.route(f"{sudo_bp.url_prefix}{bp.url_prefix}/shell/ws")
def shell_ws(ws):
    print("Starting shell...")
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
    _terminate_previous_shell(identity)

    if os.name == "nt":
        return _shell_ws_windows_pty(ws, identity)
    else:
        return _shell_ws_unix_pty(ws, identity)  # your existing PTY code

# ---------------------------
# System info
# ---------------------------

@bp.route("/jwt-to-cookie", methods=["GET"])
def jwt_to_cookie():
    # Ensure the requester already has a valid JWT (e.g., from Authorization header)
    # If you're not using headers, adjust this part accordingly.
    identity = get_jwt_identity()

    access_token = create_access_token(
        identity=identity,
        additional_claims={"perms": ["file_manager"]},
        expires_delta=timedelta(minutes=30),
    )

    resp = make_response(redirect(url_for("html_pages.admin.admin") + "#system"))

    resp.set_cookie(
        "jwt_cookie",
        access_token,          # <-- cookie value should be the token string
        max_age=60 * 60,       # 1 hour
        httponly=True,
        samesite="Lax",
        secure=True,  # set True in production (HTTPS)
        path="/",
    )

    return resp


@bp.route("/info", methods=["GET"])
def get_system_info():

    """Return basic system metrics for the admin dashboard."""
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
