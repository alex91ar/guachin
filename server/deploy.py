#!/usr/bin/env python3
from __future__ import annotations

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
from typing import Optional
import textwrap

cleaned_db = False
gunicorn_proc = None

BASE_DIR = Path(__file__).parent.resolve()
VENV_DIR = BASE_DIR / ".venv"
DATA_DIR = BASE_DIR / "data"
MYSQL_DIR = DATA_DIR / "mysql"

MYSQL_PORT = int(os.environ.get("MYSQL_PORT", "3306"))
MYSQL_USER = os.environ.get("MYSQL_USER", "guachin")
MYSQL_PASSWORD = os.environ.get("MYSQL_PASSWORD", "guachin")
MYSQL_DB = os.environ.get("MYSQL_DB", "guachin")

APP_PORT = int(os.environ.get("PORT", "5555"))

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@127.0.0.1:{MYSQL_PORT}/{MYSQL_DB}"
)

CLEAN_DB_ON_EXIT = os.environ.get("CLEAN_DB_ON_EXIT", "1")
KILL_DB_ON_EXIT = os.environ.get("KILL_DB_ON_EXIT", "1")

NGINX_CONT_NAME = os.environ.get("NGINX_CONT_NAME", "guachin-nginx")
MYSQL_CONT_NAME = os.environ.get("MYSQL_CONT_NAME", "guachin-mysql")

DOMAIN = os.environ.get("DOMAIN", "guachin.local")
TLS_PORT = int(os.environ.get("TLS_PORT", "443"))


def sh(cmd, env=None, check=True, cwd=None, capture_output=False, text=True):
    return subprocess.run(
        cmd,
        check=check,
        env=env,
        cwd=cwd,
        capture_output=capture_output,
        text=text,
    )


def kill_all_gunicorn_instances():
    print("🧹 Killing all gunicorn instances...")

    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/F", "/IM", "gunicorn.exe", "/T"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        subprocess.run(
            ["taskkill", "/F", "/IM", "python.exe", "/T"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return

    candidates = [
        ["pkill", "-9", "-f", r"gunicorn"],
        ["pkill", "-9", "-f", r"python.*-m gunicorn"],
        ["pkill", "-9", "-f", str(BASE_DIR / ".venv" / "bin" / "gunicorn")],
    ]

    for cmd in candidates:
        subprocess.run(
            cmd,
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    time.sleep(0.5)


def is_inet_up():
    try:
        with socket.create_connection(("8.8.8.8", 53), timeout=5):
            return True
    except OSError:
        return False


def create_virtualenv():
    if not VENV_DIR.exists():
        print("📦 Creating virtual environment...")
        venv.EnvBuilder(with_pip=True).create(VENV_DIR)
    else:
        print("✅ Virtual environment already exists.")


def get_venv_python():
    if sys.prefix != sys.base_prefix:
        return sys.executable

    venv_path = VENV_DIR / ("Scripts" if os.name == "nt" else "bin") / ("python.exe" if os.name == "nt" else "python")
    if venv_path.exists():
        return str(venv_path)

    raise RuntimeError("Could not find virtualenv Python.")


def get_venv_pip():
    return str(VENV_DIR / ("Scripts" if os.name == "nt" else "bin") / ("pip.exe" if os.name == "nt" else "pip"))


def pip_install_requirements():
    if not is_inet_up():
        print("ℹ️ No internet detected, skipping pip install.")
        return

    req = BASE_DIR / "requirements.txt"
    if req.exists():
        print("📚 Installing dependencies...")
        sh([get_venv_pip(), "install", "-r", str(req)])
    else:
        print("ℹ️ requirements.txt not found, skipping.")


def check_docker_installed():
    try:
        sh(["docker", "version"], check=True, capture_output=True)
        print("🐳 Docker detected.")
    except Exception:
        print("❌ Docker not found.")
        sys.exit(1)


def get_container_id_by_name_exact(name: str) -> str | None:
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


def start_mysql_local():
    os.environ["DATABASE_URL"] = DATABASE_URL

    if os.environ.get("NO_DOCKER"):
        print("⏭️ NO_DOCKER set; assuming external MySQL is running.")
        print(f"DATABASE_URL={os.environ['DATABASE_URL']}")
        return None

    check_docker_installed()
    MYSQL_DIR.mkdir(parents=True, exist_ok=True)

    existing = sh(["docker", "ps", "-a", "--format", "{{.Names}}"], capture_output=True).stdout.splitlines()
    if MYSQL_CONT_NAME in existing:
        sh(["docker", "start", MYSQL_CONT_NAME], check=False)
        print("✅ MySQL container available.")
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
        "--default-authentication-plugin=caching_sha2_password",
    ])

    return MYSQL_CONT_NAME


def _tcp_connect(host: str, port: int, timeout=1.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def wait_for_mysql(container_name: str | None, timeout: int = 60):
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

        raise TimeoutError("MySQL not reachable within timeout.")


def run_migrations() -> bool:
    alembic_ini = BASE_DIR / "alembic.ini"
    if not alembic_ini.exists():
        print("ℹ️ Alembic not configured; skipping migrations.")
        return False

    sh([get_venv_pip(), "install", "alembic"], check=False)

    alembic_exe = str(VENV_DIR / ("Scripts" if os.name == "nt" else "bin") / ("alembic.exe" if os.name == "nt" else "alembic"))
    env = os.environ.copy()
    env["DATABASE_URL"] = DATABASE_URL

    sh([alembic_exe, "upgrade", "head"], env=env, check=True)
    return True


def init_mysql_db(container_name: str | None = None, retries: int = 5, initial_delay: float = 2.0):
    print("🗄️ Ensuring DB tables exist via SQLAlchemy metadata...")
    python_exe = get_venv_python()

    code = (
        "import os; "
        "from models.db import init_engine, init_db; "
        "import models.user_session; "
        "import models.user; "
        "import models.passkey; "
        "import models.role; "
        "import models.action; "
        "import models.log; "
        "import models.agent; "
        "import models.module; "
        "import models.syscall; "
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
            sh([python_exe, "-c", code], env=env, check=True)
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
                raise


def bootstrap_app_data():
    print("🔧 Bootstrapping app data once...")
    python_exe = get_venv_python()

    code = textwrap.dedent("""
        import os
        from app import create_app
        from models.db import init_engine
        from models.schema import populate_actions_from_routes, load_modules_from_directory

        url = os.environ.get("DATABASE_URL")
        if not url:
            raise RuntimeError("DATABASE_URL is not set")

        init_engine(url)
        app = create_app()

        with app.app_context():
            populate_actions_from_routes(app)
            load_modules_from_directory()

        print("✅ Bootstrap complete.")
    """)

    env = os.environ.copy()
    env["DATABASE_URL"] = DATABASE_URL
    sh([python_exe, "-c", code], env=env, check=True)


def terminate_process(proc: subprocess.Popen | None, name: str):
    if not proc or proc.poll() is not None:
        return

    print(f"🛑 Stopping {name} (pid={proc.pid})...")
    try:
        proc.kill()
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        print(f"⚠️ {name} did not stop gracefully, killing...")
        proc.kill()
        proc.wait(timeout=5)


def start_flask_app_gunicorn():
    global gunicorn_proc

    print("🚀 Starting Flask app with Gunicorn...")
    gunicorn_cmd = [
        get_venv_python(),
        "-m",
        "gunicorn",
        "--bind", f"127.0.0.1:{APP_PORT}",
        "--workers", "1",
        "--threads", "4",
        "--reload",
        "--graceful-timeout", "1",
        "--access-logfile", "-",
        "--error-logfile", "-",
        "app:create_app()",
    ]

    gunicorn_proc = subprocess.Popen(
        gunicorn_cmd,
        stdout=None,
        stderr=None,
    )
    return gunicorn_proc


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

    return "127.0.0.1"


def hosts_file_path() -> Path:
    if os.name == "nt":
        return Path(os.environ.get("SystemRoot", r"C:\\Windows")) / "System32" / "drivers" / "etc" / "hosts"
    return Path("/etc/hosts")


def file_contains_line(path: Path | str, line: str) -> bool:
    p = Path(path)
    if not p.exists() or not p.is_file():
        return False

    target = line.strip()
    try:
        with p.open("r", encoding="utf-8", errors="ignore") as f:
            for existing_line in f:
                if existing_line.strip() == target:
                    return True
    except Exception:
        return False

    return False


def add_hosts_entry(domain: str, ip: str):
    line = f"{ip}\t{domain}"
    hosts_path = hosts_file_path()

    if file_contains_line(hosts_path, line):
        print(f"✅ Hosts entry already exists: {line}")
        return

    print(f"🧭 Add this line to {hosts_path} if needed:")
    print(line)


def generate_self_signed_cert_via_docker(cert_dir: Path, domain: str):
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

    print(f"🔐 Generating self-signed TLS cert for {domain} ...")
    sh([
        "docker", "run", "--rm",
        "-v", f"{cert_dir}:/cert",
        "alpine:3.19",
        "sh", "-lc",
        "apk add --no-cache openssl >/dev/null "
        "&& openssl req -x509 -nodes -days 365 -newkey rsa:2048 "
        "-keyout /cert/key.pem -out /cert/cert.pem -config /cert/openssl.cnf"
    ], check=True)

    return crt, key


def write_nginx_default_conf(conf_dir: Path, domain: str, tls_port: int, upstream_port: int):
    conf_dir.mkdir(parents=True, exist_ok=True)
    conf = conf_dir / "default.conf"

    conf.write_text(
        f"""
server {{
    listen 80;
    server_name {domain};

    location /api/v1/anon/agent/ws/ {{
        proxy_pass http://host.docker.internal:{upstream_port};
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-Proto http;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_read_timeout 3600;
        proxy_send_timeout 3600;
        proxy_buffering off;
    }}

    location / {{
        return 301 https://$host:{tls_port}$request_uri;
    }}
}}

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
        proxy_pass http://host.docker.internal:{upstream_port};
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
        proxy_set_header Connection "upgrade";
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


def docker_run_nginx(domain: str, tls_port: int, cert_dir: Path, conf_dir: Path):
    check_docker_installed()

    existing_id = get_container_id_by_name_exact(NGINX_CONT_NAME)
    if existing_id:
        subprocess.run(["docker", "rm", "-f", NGINX_CONT_NAME], check=False)

    cmd = [
        "docker", "run", "-d",
        "--name", NGINX_CONT_NAME,
        "-p", "80:80",
        "-p", f"{tls_port}:{tls_port}",
        "-v", f"{cert_dir}:/etc/nginx/certs:ro",
        "-v", f"{conf_dir}:/etc/nginx/conf.d:ro",
    ]

    if os.name != "nt":
        cmd += ["--add-host=host.docker.internal:host-gateway"]

    cmd += ["nginx:alpine"]

    sh(cmd, check=True)
    return True


def start_nginx_dev_docker(domain: str, upstream_port: int = 5555):
    local_ip = get_local_non_loopback_ip()
    print(f"🧭 Local IP chosen for hosts entry: {local_ip}")

    add_hosts_entry(domain, local_ip)

    root_dir = DATA_DIR / "nginx-dev" / domain
    cert_dir = root_dir / "cert"
    conf_dir = root_dir / "conf"

    crt, key = generate_self_signed_cert_via_docker(cert_dir, domain)
    if not crt or not key:
        print("⚠️ TLS cert not available; skipping nginx docker start.")
        return None

    write_nginx_default_conf(
        conf_dir=conf_dir,
        domain=domain,
        tls_port=TLS_PORT,
        upstream_port=upstream_port,
    )

    print(
        f"🌐 Starting nginx (Docker) https://{domain}:{TLS_PORT} "
        f"-> Flask http://host.docker.internal:{upstream_port}"
    )
    docker_run_nginx(domain, TLS_PORT, cert_dir, conf_dir)
    time.sleep(0.5)

    if get_container_id_by_name_exact(NGINX_CONT_NAME):
        os.environ["WEBAUTHN_ORIGIN"] = f"https://{domain}:{TLS_PORT}"
        return {"domain": domain, "tls_port": TLS_PORT, "ip": local_ip}

    print("❌ Failed to start nginx.")
    return None


def stop_nginx_dev_docker():
    cid = get_container_id_by_name_exact(NGINX_CONT_NAME)
    if cid:
        print("🛑 Stopping nginx (Docker)...")
        subprocess.run(["docker", "rm", "-f", NGINX_CONT_NAME], check=False)


def clean_database(container_name: str | None):
    global cleaned_db
    if cleaned_db:
        return
    cleaned_db = True

    if KILL_DB_ON_EXIT != "1":
        print("🧯 KILL_DB_ON_EXIT=0 — keeping database/container.")
        return

    stop_nginx_dev_docker()

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


def run_dev():
    print("=== 🚀 Dev bootstrap ===")
    kill_all_gunicorn_instances()
    create_virtualenv()
    pip_install_requirements()

    container_name = start_mysql_local()
    wait_for_mysql(container_name)

    migrations_attempted = run_migrations()
    if not migrations_attempted:
        init_mysql_db(container_name=container_name)

    bootstrap_app_data()

    gunicorn_proc = start_flask_app_gunicorn()
    proxy_info = start_nginx_dev_docker(domain=DOMAIN, upstream_port=APP_PORT)

    def shutdown():
        print("\n🛑 Shutting down...")
        stop_nginx_dev_docker()
        terminate_process(gunicorn_proc, "gunicorn")
        kill_all_gunicorn_instances()
        if CLEAN_DB_ON_EXIT == "1":
            clean_database(container_name)
        print("✅ Clean exit.")
        if proxy_info:
            print(f"ℹ️ Dev origin: https://{proxy_info['domain']}:{proxy_info['tls_port']}")

    def handle_signal(signum, frame):
        shutdown()
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    try:
        while True:
            if gunicorn_proc and gunicorn_proc.poll() is not None:
                print(f"⚠️ Gunicorn exited with code {gunicorn_proc.returncode}")
                break
            time.sleep(1)
    finally:
        shutdown()


def run_prod():
    print("=== 🚀 Production bootstrap ===")
    kill_all_gunicorn_instances()
    create_virtualenv()
    pip_install_requirements()

    ran = run_migrations()
    if not ran:
        init_mysql_db(container_name=None)

    bootstrap_app_data()

    print("✅ Production setup complete.")


def main():
    parser = argparse.ArgumentParser(description="Deploy the app.")
    parser.add_argument("env", choices=["dev", "prod"], help="Environment to run.")
    args = parser.parse_args()

    if args.env == "dev":
        run_dev()
    else:
        run_prod()


if __name__ == "__main__":
    main()