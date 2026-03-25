#!/usr/bin/env python3
import os
import subprocess
import sys
import time
import venv
import argparse
import shutil
import signal
import socket
from pathlib import Path
import shlex
from typing import Sequence, Union
from pathlib import Path

cleaned_db = False

def file_contains_line(path: Path | str, line: str) -> bool:
    """
    Returns True if the file contains the given line (exact match, ignoring
    leading/trailing whitespace). Returns False if file doesn't exist.
    """
    p = Path(path)
    if not p.exists() or not p.is_file():
        return False

    target = line.strip()

    try:
        with p.open("r", encoding="utf-8", errors="ignore") as f:
            for l in f:
                if l.strip() == target:
                    return True
    except Exception:
        return False

    return False

BASE_DIR = Path(__file__).parent.resolve()
VENV_DIR = BASE_DIR / ".venv"
DATA_DIR = BASE_DIR / "data"
MYSQL_DIR = DATA_DIR / "mysql"

MYSQL_PORT = int(os.environ.get("MYSQL_PORT", "3306"))
MYSQL_USER = os.environ.get("MYSQL_USER", "guachin")
MYSQL_PASSWORD = os.environ.get("MYSQL_PASSWORD", "guachin")
MYSQL_DB = os.environ.get("MYSQL_DB", "guachin")

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@127.0.0.1:{MYSQL_PORT}/{MYSQL_DB}"
)

CLEAN_DB_ON_EXIT = os.environ.get("CLEAN_DB_ON_EXIT", "1")  # "1" to clean, "0" to keep
KILL_DB_ON_EXIT = os.environ.get("KILL_DB_ON_EXIT", "1")    # "1" to drop schema on exit (external DB path)

VEN_CREATED_THIS_RUN = False

NGINX_CONT_NAME = os.environ.get("NGINX_CONT_NAME", "guachin-nginx")
MYSQL_CONT_NAME = os.environ.get("MYSQL_CONT_NAME", "guachin-mysql")

def run_elevated(cmd: Union[str, Sequence[str]], cwd: str | None = None, env: dict | None = None) -> int:
    """
    Run a command with elevation (UAC on Windows, sudo on Unix).
    Returns the process exit code.

    - On Windows: opens an elevated process (UAC prompt).
    - On Unix/macOS: runs with sudo (prompts in the terminal).

    Notes:
    - On Windows, this creates a *new* elevated process; output won't stream back here.
    - If you need output capture, you generally shouldn't elevate that way; instead elevate the whole script.
    """
    if isinstance(cmd, str):
        cmd_list = shlex.split(cmd, posix=(os.name != "nt"))
    else:
        cmd_list = list(cmd)

    if os.name == "nt":
        # Build a single command line for Start-Process
        exe = cmd_list[0]
        args = cmd_list[1:]

        # Quote args safely for PowerShell
        def ps_quote(s: str) -> str:
            # PowerShell single-quote escaping: '' inside ''
            return "'" + s.replace("'", "''") + "'"

        ps_args = " ".join(ps_quote(a) for a in args)
        ps_cwd = ps_quote(cwd) if cwd else "$PWD"

        # Pass environment by inheriting current env. If you need custom env, prefer elevating the whole script.
        ps = [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy", "Bypass",
            "-Command",
            f"Start-Process -FilePath {ps_quote(exe)} -ArgumentList {ps_quote(ps_args)} -Verb RunAs -WorkingDirectory {ps_cwd}; exit 0"
        ]
        # This returns 0 if the Start-Process command ran; it doesn't reflect child exit status.
        return subprocess.run(ps, cwd=cwd, env=env).returncode

    else:
        # Unix/macOS: sudo will prompt for password in the terminal if required.
        sudo_cmd = ["sudo", "-k"] + cmd_list
        return subprocess.run(sudo_cmd, cwd=cwd, env=env).returncode

# ---------------------------
# Helpers
# ---------------------------

def sh(cmd, env=None, check=True, cwd=None, capture_output=False, text=True):
    print("➤", " ".join(map(str, cmd)))
    return subprocess.run(
        cmd, check=check, env=env, cwd=cwd, capture_output=capture_output, text=text
    )

def is_inet_up():
    TARGET = "8.8.8.8"
    PORT = 53  # Port used for DNS queries
    TIMEOUT = 5
    
    try:
        with socket.create_connection((TARGET, PORT), timeout=TIMEOUT):
            return True
    except OSError:
        return False


def which(cmd: str) -> bool:
    return shutil.which(cmd) is not None


def which(cmd: str) -> bool:
    return shutil.which(cmd) is not None


def create_virtualenv():
    global VEN_CREATED_THIS_RUN
    if not VENV_DIR.exists():
        print("📦 Creating virtual environment...")
        venv.EnvBuilder(with_pip=True).create(VENV_DIR)
        VEN_CREATED_THIS_RUN = True
    else:
        print("✅ Virtual environment already exists.")


def pip_install_requirements():
    if not is_inet_up():
        print("No internet, trying to skip pip install...")
        return
    print("📚 Installing dependencies...")
    pip_exe = VENV_DIR / ("Scripts" if os.name == "nt" else "bin") / ("pip.exe" if os.name == "nt" else "pip")
    req = BASE_DIR / "requirements.txt"
    if req.exists():
        sh([str(pip_exe), "install", "-r", str(req)])
    else:
        print("ℹ️ requirements.txt not found, skipping.")


def check_docker_installed():
    try:
        sh(["docker", "version"], check=True, capture_output=True)
        print("🐳 Docker detected.")
        return True
    except Exception:
        print("❌ Docker not found. Set NO_DOCKER=1 to use an external MySQL or install Docker:")
        print("   https://docs.docker.com/get-docker/")
        sys.exit(1)


def get_container_id_by_name_exact(name: str) -> str | None:
    """
    Returns the Docker container ID for an EXACT container name.
    Returns None if not found.
    """
    if not name:
        return None
    try:
        result = subprocess.run(
            ["docker", "ps", "-aq", "--filter", f"name=^/{name}$"],
            capture_output=True,
            text=True,
            check=True,
        )
        cid = result.stdout.strip()
        return cid or None
    except Exception:
        return None


# ---------------------------
# MySQL
# ---------------------------

def start_mysql_local():
    """Start mysql:8.0 in Docker unless NO_DOCKER is set. Returns container name or None."""
    os.environ["SQLALCHEMY_DATABASE_URI"] = (
        f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@127.0.0.1:{MYSQL_PORT}/{MYSQL_DB}"
    )
    os.environ["DATABASE_URL"] = os.environ["SQLALCHEMY_DATABASE_URI"]

    if os.environ.get("NO_DOCKER"):
        print("⏭️  NO_DOCKER set; assuming external MySQL is running.")
        print(f"SQLALCHEMY_DATABASE_URI={os.environ['SQLALCHEMY_DATABASE_URI']}")
        return None

    check_docker_installed()
    MYSQL_DIR.mkdir(parents=True, exist_ok=True)

    existing = sh(["docker", "ps", "-a", "--format", "{{.Names}}"], capture_output=True).stdout.splitlines()
    if MYSQL_CONT_NAME in existing:
        sh(["docker", "start", MYSQL_CONT_NAME], check=False)
        print("✅ MySQL container available.")
        print(f"SQLALCHEMY_DATABASE_URI={os.environ['SQLALCHEMY_DATABASE_URI']}")
        return MYSQL_CONT_NAME

    print(f"🚀 Starting MySQL on port {MYSQL_PORT} (container: {MYSQL_CONT_NAME})...")
    sh([
        "docker", "run", "-d",
        "--name", MYSQL_CONT_NAME,
        "-e", f"MYSQL_USER={MYSQL_USER}",
        "-e", f"MYSQL_PASSWORD={MYSQL_PASSWORD}",
        "-e", f"MYSQL_DATABASE={MYSQL_DB}",
        "-e", f"MYSQL_ROOT_PASSWORD={MYSQL_PASSWORD}",
        "-p", f"{MYSQL_PORT}:3306",
        "-v", f"{MYSQL_DIR}:/var/lib/mysql",
        "mysql:8.0",
        "--default-authentication-plugin=caching_sha2_password"
    ])
    print(f"SQLALCHEMY_DATABASE_URI={os.environ['SQLALCHEMY_DATABASE_URI']}")
    return MYSQL_CONT_NAME


def _tcp_connect(host: str, port: int, timeout=1.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def wait_for_mysql(container_name: str | None, timeout: int = 60):
    """Wait until MySQL accepts connections."""
    print("⏳ Waiting for MySQL to become ready...")
    start = time.time()

    if container_name:
        while time.time() - start < timeout:
            res = subprocess.run(
                ["docker", "exec", container_name, "mysqladmin", "ping",
                 "-u", MYSQL_USER, f"-p{MYSQL_PASSWORD}", "--silent"],
                capture_output=True, text=True
            )
            if res.returncode == 0:
                print("✅ MySQL is ready.")
                return
            time.sleep(1)
        print(res.stdout or res.stderr)
        raise TimeoutError("MySQL did not become ready in time.")
    else:
        while time.time() - start < timeout:
            if _tcp_connect("127.0.0.1", MYSQL_PORT):
                print("✅ MySQL is reachable on TCP.")
                return
            time.sleep(1)
        raise TimeoutError("MySQL (external) not reachable on TCP within timeout.")


def run_migrations() -> bool:
    """Run Alembic migrations if configured. Returns True if migrations attempted."""
    alembic_ini = BASE_DIR / "alembic.ini"
    if not alembic_ini.exists():
        print("ℹ️ Alembic not configured (alembic.ini missing); skipping migrations.")
        return False

    pip_exe = VENV_DIR / ("Scripts" if os.name == "nt" else "bin") / ("pip.exe" if os.name == "nt" else "pip")
    sh([str(pip_exe), "install", "alembic"], check=False)

    alembic_exe = VENV_DIR / ("Scripts" if os.name == "nt" else "bin") / ("alembic.exe" if os.name == "nt" else "alembic")
    env = os.environ.copy()
    env["DATABASE_URL"] = DATABASE_URL
    print("📜 Running Alembic migrations...")
    sh([str(alembic_exe), "upgrade", "head"], env=env, check=False)
    print("✅ Migrations completed (or no changes).")
    return True


def init_mysql_db(container_name: str | None = None, retries: int = 5, initial_delay: float = 2.0):
    print("🗄️  Ensuring MySQL tables exist via SQLAlchemy metadata (with retry)...")
    python_exe = VENV_DIR / ("Scripts" if os.name == "nt" else "bin") / ("python.exe" if os.name == "nt" else "python")
    code = (
        "import os; "
        "from models.db import init_engine, init_db; "
        "from models import user_session, user, passkey, role, action, log, agent, request, response; "
        "url = os.environ.get('DATABASE_URL'); "
        "print('Initializing DB...'); "
        "init_engine(url); "
        "init_db(drop_all=False); "
        "print('✅ Database tables ensured.')"
    )
    env = os.environ.copy()
    env["DATABASE_URL"] = DATABASE_URL
    delay = initial_delay

    for attempt in range(1, retries + 1):
        try:
            sh([str(python_exe), "-c", code], env=env, check=True)
            print(f"✅ init_mysql_db succeeded on attempt {attempt}.")
            return
        except subprocess.CalledProcessError:
            print(f"⚠️ init_mysql_db failed (attempt {attempt}/{retries}).")
            try:
                wait_for_mysql(container_name, timeout=15)
            except Exception as ready_err:
                print(f"ℹ️ Readiness recheck before retry: {ready_err}")
            if attempt < retries:
                print(f"⏳ Retrying in {delay:.1f}s...")
                time.sleep(delay)
                delay *= 1.5
            else:
                print("❌ Exhausted retries for init_mysql_db.")
                raise


import textwrap

def reset_external_db_schema():
    print(f"🧨 Resetting external MySQL DB (DROP DATABASE {MYSQL_DB} ...)...")

    python_exe = (
        VENV_DIR
        / ("Scripts" if os.name == "nt" else "bin")
        / ("python.exe" if os.name == "nt" else "python")
    )

    code = textwrap.dedent("""
        import os
        from sqlalchemy import create_engine, text

        url = os.environ["DATABASE_URL"]
        server_url = url.rsplit("/", 1)[0]
        db = os.environ.get("MYSQL_DB", "guachin-NG")

        engine = create_engine(server_url, future=True, echo=True, pool_recycle=30, pool_pre_ping=True)

        with engine.connect() as c:
            c = c.execution_options(isolation_level="AUTOCOMMIT")
            c.execute(text(f"DROP DATABASE IF EXISTS `{db}`"))
            c.execute(text(f"CREATE DATABASE `{db}`"))

        print("✅ External DB reset.")
    """)

    env = os.environ.copy()
    env["DATABASE_URL"] = DATABASE_URL
    env["MYSQL_DB"] = MYSQL_DB

    try:
        sh([str(python_exe), "-c", code], env=env, check=True)
    except Exception as e:
        print(f"⚠️ Failed to reset external MySQL DB: {e}")



def clean_database(container_name: str | None):
    global cleaned_db
    if cleaned_db:
        return
    cleaned_db = True
    if CLEAN_DB_ON_EXIT == "1":
        reset_external_db_schema()
        print("🧯 CLEAN_DB_ON_EXIT=1 — cleaned.")
    if KILL_DB_ON_EXIT != "1":
        print("🧯 KILL_DB_ON_EXIT=0 — keeping database.")
    

    if container_name:
        print("🧹 Cleaning Dockerized MySQL data...")
        subprocess.run(["docker", "stop", container_name], check=False)
        subprocess.run(["docker", "rm", container_name], check=False)
        try:
            if MYSQL_DIR.exists():
                shutil.rmtree(MYSQL_DIR, ignore_errors=True)
                print(f"✅ Removed {MYSQL_DIR}")
        except Exception as e:
            print(f"⚠️ Failed to remove {MYSQL_DIR}: {e}")
    else:
        print("🧹 Cleaning external MySQL (NO_DOCKER=1) ...")
        reset_external_db_schema()
    


def clean_all_docker_containers_keep_exact(keep_names: list[str]):
    """
    Stop + remove ALL Docker containers except those with exact names in keep_names.
    Cross-platform; avoids shell $(...) stuff.
    """
    if os.environ.get("NO_DOCKER"):
        print("⏭️ NO_DOCKER set; skipping global Docker container cleanup.")
        return

    try:
        check_docker_installed()
    except SystemExit:
        return

    keep_ids = set()
    for name in keep_names:
        cid = get_container_id_by_name_exact(name)
        if cid:
            keep_ids.add(cid)

    result = subprocess.run(["docker", "ps", "-aq"], capture_output=True, text=True, check=False)
    ids = [cid.strip() for cid in result.stdout.splitlines() if cid.strip()]
    ids = [cid for cid in ids if cid not in keep_ids]

    if not ids:
        print("ℹ️ No Docker containers to remove (after keep list).")
        return

    print(f"🧹 Removing {len(ids)} Docker container(s) (keeping exact: {keep_names})...")
    sh(["docker", "rm", "-f", *ids], check=False)
    print("✅ Docker cleanup done.")


# ---------------------------
# Dev nginx via Docker + hosts + TLS (WebAuthn-friendly)
# ---------------------------

def get_local_non_loopback_ip() -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        if ip and ip != "127.0.0.1":
            return ip
    except Exception:
        pass
    finally:
        s.close()

    try:
        ip = socket.gethostbyname(socket.gethostname())
        if ip and ip != "127.0.0.1":
            return ip
    except Exception:
        pass

    return "192.168.1.10"


def hosts_file_path() -> Path:
    if os.name == "nt":
        return Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "drivers" / "etc" / "hosts"
    return Path("/etc/hosts")


def add_hosts_entry(domain: str, ip: str):
    """
    Add/update hosts entry: ip domain
    Requires admin/root. Best effort; prints manual instruction if denied.
    """
    print(f"Adding host entry {domain} as {ip}.")
    hosts_path = "C:\\Windows\\System32\\drivers\\etc\\hosts" if os.name == "nt" else "/etc/hosts"
    line = f"{ip}\t{domain}"
    if file_contains_line(hosts_path, line):
        print("Host entry already entered.")
        return
    if os.name == "nt":
        # Append line using cmd.exe (needs admin)
        print("Returned = " + str(run_elevated(["cmd", "/c", f'echo {line}>> "{hosts_path}"'])))
    else:
        # Append line using shell (needs sudo). Safer to use tee.
        print("Returned = " + str(run_elevated(["sh", "-c", f'printf "\\n{line}\\n" | tee -a "{hosts_path}" >/dev/null'])))



def generate_self_signed_cert_via_docker(cert_dir: Path, domain: str):
    """
    Creates cert.pem and key.pem using a one-shot Docker container (alpine + openssl).
    Works even if OpenSSL isn't installed locally.
    """
    check_docker_installed()
    cert_dir.mkdir(parents=True, exist_ok=True)
    crt = cert_dir / "cert.pem"
    key = cert_dir / "key.pem"
    cnf = cert_dir / "openssl.cnf"

    if crt.exists() and key.exists():
        print("✅ Dev TLS cert already exists.")
        return crt, key

    cnf.write_text(
        "\n".join([
            "[req]",
            "default_bits=2048",
            "prompt=no",
            "default_md=sha256",
            "distinguished_name=dn",
            "req_extensions=req_ext",
            "",
            "[dn]",
            f"CN={domain}",
            "",
            "[req_ext]",
            "subjectAltName=@alt_names",
            "",
            "[alt_names]",
            f"DNS.1={domain}",
        ]) + "\n",
        encoding="utf-8",
    )

    print(f"🔐 Generating self-signed TLS cert for {domain} (via Docker) ...")

    # Use alpine to install openssl and generate cert with SAN
    sh([
        "docker", "run", "--rm",
        "-v", f"{cert_dir}:/cert",
        "alpine:3.19",
        "sh", "-lc",
        "apk add --no-cache openssl >/dev/null "
        "&& openssl req -x509 -nodes -days 365 -newkey rsa:2048 "
        "-keyout /cert/key.pem -out /cert/cert.pem -config /cert/openssl.cnf"
    ], check=True)

    if not crt.exists() or not key.exists():
        print("❌ Failed to generate cert/key in:", cert_dir)
        return None, None

    print(f"✅ Generated: {crt} and {key}")
    return crt, key


def write_nginx_default_conf(conf_dir: Path, domain: str, tls_port: int, upstream_port: int):
    """
    Writes /etc/nginx/conf.d/default.conf equivalent to a host directory.
    Proxy target is host.docker.internal:<upstream_port>
    """
    conf_dir.mkdir(parents=True, exist_ok=True)
    conf = conf_dir / "default.conf"

    conf.write_text(
        f"""
    server {{
        listen {tls_port} ssl;
        server_name {domain};

        ssl_certificate     /etc/nginx/certs/cert.pem;
        ssl_certificate_key /etc/nginx/certs/key.pem;

        ssl_session_cache shared:SSL:10m;

        location / {{
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto https;

            proxy_pass http://host.docker.internal:{upstream_port};
        }}
        location /api/v1/auth/agent/ws/ {{
        proxy_pass http://host.docker.internal:{ upstream_port };
        proxy_http_version 1.1;

        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";

        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;

        proxy_read_timeout 3600;
        proxy_send_timeout 3600;
        proxy_buffering off;
        }}

        location /api/v1/anon/agent/ws/ {{
        proxy_pass http://host.docker.internal:{ upstream_port };
        proxy_http_version 1.1;

        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";

        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;

        proxy_read_timeout 3600;
        proxy_send_timeout 3600;
        proxy_buffering off;
        }}

        location /api/v1/auth/sudo/system/shell/ws {{
                proxy_pass http://host.docker.internal:{upstream_port};
                proxy_http_version 1.1;

                proxy_set_header Upgrade $http_upgrade;
                proxy_set_header Connection "Upgrade";

                proxy_set_header Host $host;
                proxy_set_header X-Real-IP $remote_addr;
                proxy_set_header X-Forwarded-Proto $scheme;
                proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;

                proxy_read_timeout 3600;
                proxy_send_timeout 3600;
                proxy_buffering off;
            }}
    }}
""".strip() + "\n",
        encoding="utf-8",
    )
    return conf


def docker_run_nginx(domain: str, tls_port: int, upstream_port: int, cert_dir: Path, conf_dir: Path):
    """
    Starts nginx container with mounted certs + conf.
    On Linux, adds host.docker.internal mapping using host-gateway.
    """
    check_docker_installed()

    # Remove existing container if any
    existing_id = get_container_id_by_name_exact(NGINX_CONT_NAME)
    if existing_id:
        subprocess.run(["docker", "rm", "-f", NGINX_CONT_NAME], check=False)

    cmd = [
        "docker", "run", "-d",
        "--name", NGINX_CONT_NAME,
        "-p", f"{tls_port}:{tls_port}",
        "-v", f"{cert_dir}:/etc/nginx/certs:ro",
        "-v", f"{conf_dir}:/etc/nginx/conf.d:ro",
    ]

    # Linux needs this for host.docker.internal to work
    if os.name != "nt":
        # This is supported by Docker Desktop and modern Docker on Linux
        cmd += ["--add-host=host.docker.internal:host-gateway"]

    cmd += ["nginx:alpine"]

    sh(cmd, check=True)
    return True


def start_nginx_dev_docker(domain: str, upstream_port: int = 5555):
    """
    Start nginx in Docker to provide https://<domain> for WebAuthn.
    Adds hosts entry <domain> -> local LAN IP (not 127.0.0.1).
    Generates a self-signed TLS cert via Docker.
    Binds 443 first, then falls back to 8443.
    """
    local_ip = get_local_non_loopback_ip()
    print(f"🧭 Local IP chosen for hosts entry: {local_ip}")

    # Add hosts entry (may require admin/root)
    add_hosts_entry(domain, local_ip)

    root_dir = DATA_DIR / "nginx-dev" / domain
    cert_dir = root_dir / "cert"
    conf_dir = root_dir / "conf"

    crt, key = generate_self_signed_cert_via_docker(cert_dir, domain)
    if not crt or not key:
        print("⚠️ TLS cert not available; skipping nginx docker start.")
        return None

    for tls_port in (443, 8443):
        write_nginx_default_conf(conf_dir, domain, tls_port, upstream_port)
        try:
            print(f"🌐 Starting nginx (Docker) https://{domain}:{tls_port} -> http://host.docker.internal:{upstream_port}")
            docker_run_nginx(domain, tls_port, upstream_port, cert_dir, conf_dir)
            time.sleep(0.5)
            # Quick health-ish check: container still exists
            if get_container_id_by_name_exact(NGINX_CONT_NAME):
                print(f"✅ nginx container running. Open: https://{domain}:{tls_port}")
                os.environ["WEBAUTHN_ORIGIN"] = f"https://{domain}:{tls_port}"
                return {"domain": domain, "tls_port": tls_port, "ip": local_ip}
        except Exception as e:
            print(f"⚠️ Failed to start nginx on port {tls_port}: {e}")
            subprocess.run(["docker", "rm", "-f", NGINX_CONT_NAME], check=False)

    print("❌ Could not start nginx on 443 or 8443.")
    return None


def stop_nginx_dev_docker():
    cid = get_container_id_by_name_exact(NGINX_CONT_NAME)
    if cid:
        print("🛑 Stopping nginx (Docker)...")
        subprocess.run(["docker", "rm", "-f", NGINX_CONT_NAME], check=False)


# ---------------------------
# Flask runner
# ---------------------------

def run_flask_app():
    print("🌐 Starting Flask app in debug mode...")
    python_exe = VENV_DIR / ("Scripts" if os.name == "nt" else "bin") / ("python.exe" if os.name == "nt" else "python")
    env = os.environ.copy()
    env.update({
        "FLASK_ENV": "development",
        "DATABASE_URL": DATABASE_URL,
        "INIT_DB_ON_START": "0",
        # Ensure WebAuthn RP ID is set for dev
        "WEBAUTHN_RP_ID": env.get("WEBAUTHN_RP_ID", env.get("DOMAIN", "guachin.local")),
    })
    subprocess.run([str(python_exe), "app.py"], env=env)


# ---------------------------
# Environments
# ---------------------------

def run_dev():
    print("=== 🚀 Starting Development (MySQL + Alembic/InitDB + nginx Docker TLS for WebAuthn) ===")
    create_virtualenv()
    pip_install_requirements()

    # Start DB
    container_name = start_mysql_local()
    wait_for_mysql(container_name)

    migrations_attempted = run_migrations()
    if not migrations_attempted:
        init_mysql_db(container_name=container_name)

    # nginx via Docker + hosts + TLS
    rp_id = os.environ.get("WEBAUTHN_RP_ID") or os.environ.get("DOMAIN") or "guachin.local"
    proxy_info = start_nginx_dev_docker(domain=rp_id, upstream_port=int(os.environ.get("PORT", "5555")))

    def handle_sigint(signum, frame):
        print("\n🛑 Caught Ctrl+C, shutting down...")
        stop_nginx_dev_docker()
        clean_database(container_name)
        # keep mysql? up to you. here we keep none by default
        clean_all_docker_containers_keep_exact([MYSQL_CONT_NAME])  # keeps mysql exact name only
        print("👋 Goodbye.")
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_sigint)

    try:
        run_flask_app()
    finally:
        print("🛑 Shutting down...")
        stop_nginx_dev_docker()
        clean_database(container_name)
        clean_all_docker_containers_keep_exact([MYSQL_CONT_NAME])  # keeps mysql exact name only
        print("✅ Clean exit.")

        if proxy_info:
            d = proxy_info["domain"]
            p = proxy_info["tls_port"]
            print(f"ℹ️ Dev WebAuthn origin was: https://{d}:{p}")


def run_prod():
    print("=== 🚀 Production bootstrap ===")
    create_virtualenv()
    pip_install_requirements()
    try:
        ran = run_migrations()
        if not ran:
            print("⚠️ Alembic not configured in prod. Please set up migrations.")
            sys.exit(1)
    except Exception as e:
        print(f"⚠️ Migration failed: {e}")
        sys.exit(1)
    print("✅ Production setup complete. Start your WSGI/ASGI server with DATABASE_URL configured.")


def main():
    parser = argparse.ArgumentParser(description="Deploy the guachin application.")
    parser.add_argument("env", choices=["dev", "prod"], help="Environment to run.")
    args = parser.parse_args()

    if args.env == "dev":
        run_dev()
    else:
        run_prod()


if __name__ == "__main__":
    main()
