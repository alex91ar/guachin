#!/usr/bin/env bash
set -euo pipefail

# -------------------------
# DEV MODE: nginx + hosts + TLS for WEBAUTHN_RP_ID
# -------------------------

DEV_MODE="${DEV_MODE:-0}"     # set DEV_MODE=1 to enable
FLASK_PORT="${FLASK_PORT:-5000}"
NGINX_SITE_NAME="${NGINX_SITE_NAME:-webauthn-dev}"
CERT_DIR="${CERT_DIR:-/etc/nginx/certs}"

need_root() {
  if [ "$(id -u)" -ne 0 ]; then
    if command -v sudo >/dev/null 2>&1; then
      sudo -v
      SUDO="sudo"
    else
      echo "❌ This step needs root but sudo is not available."
      exit 1
    fi
  else
    SUDO=""
  fi
}

# Best-effort RP ID resolver:
# 1) Use env WEBAUTHN_RP_ID if set
# 2) Else: try python to import your config and print it
get_rp_id() {
  if [ -n "${WEBAUTHN_RP_ID:-}" ]; then
    echo "$WEBAUTHN_RP_ID"
    return 0
  fi

  if command -v python >/dev/null 2>&1; then
    python - <<'PY' 2>/dev/null || true
import os
try:
  # adjust imports if your config module path differs
  from config import config
  print(config.get("WEBAUTHN_RP_ID") or "")
except Exception:
  print("")
PY
  fi
}

# Pick any non-loopback local IP
get_local_ip() {
  # Linux (iproute2)
  if command -v ip >/dev/null 2>&1; then
    # Default-route interface address (usually correct)
    ip route get 1.1.1.1 2>/dev/null | awk '{for (i=1;i<=NF;i++) if ($i=="src") {print $(i+1); exit}}' || true
    return 0
  fi

  # macOS (ipconfig)
  if command -v ipconfig >/dev/null 2>&1; then
    # common interfaces
    ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || true
    return 0
  fi

  # Fallback: first non-127 address from hostname -I (Linux)
  if command -v hostname >/dev/null 2>&1; then
    hostname -I 2>/dev/null | tr ' ' '\n' | grep -vE '^127\.' | head -n 1 || true
    return 0
  fi
}

install_nginx() {
  if command -v nginx >/dev/null 2>&1; then
    echo "✅ nginx already installed"
    return
  fi

  echo "📦 Installing nginx..."
  if [ -f /etc/debian_version ]; then
    $SUDO apt-get update -y
    $SUDO apt-get install -y nginx openssl
  elif [ -f /etc/redhat-release ] || command -v dnf >/dev/null 2>&1; then
    $SUDO dnf install -y nginx openssl || $SUDO yum install -y nginx openssl
  elif command -v pacman >/dev/null 2>&1; then
    $SUDO pacman -Sy --noconfirm nginx openssl
  elif command -v brew >/dev/null 2>&1; then
    brew install nginx openssl
  else
    echo "❌ Unsupported OS/package manager. Install nginx manually."
    exit 1
  fi
}

add_hosts_entry() {
  local domain="$1"
  local ip="$2"

  if [ -z "$domain" ] || [ -z "$ip" ]; then
    echo "❌ add_hosts_entry: missing domain or ip"
    exit 1
  fi

  if [[ "$ip" =~ ^127\. ]]; then
    echo "❌ Local IP resolved to loopback ($ip). Need a non-127 IP for WebAuthn."
    exit 1
  fi

  echo "🧾 Ensuring /etc/hosts maps $domain -> $ip"
  need_root

  # Remove any existing lines for that domain, then add our desired one
  $SUDO sh -c "cp /etc/hosts /etc/hosts.bak.$(date +%s)"
  $SUDO sh -c "grep -vE '[[:space:]]$domain([[:space:]]|\$)' /etc/hosts > /tmp/hosts.$$ && mv /tmp/hosts.$$ /etc/hosts"
  $SUDO sh -c "printf '%s\t%s\n' '$ip' '$domain' >> /etc/hosts"
}

make_self_signed_cert() {
  local domain="$1"
  local cert_dir="$2"

  echo "🔐 Creating self-signed TLS cert for $domain"
  need_root
  $SUDO mkdir -p "$cert_dir"

  local key="$cert_dir/${domain}.key"
  local crt="$cert_dir/${domain}.crt"

  if [ -f "$key" ] && [ -f "$crt" ]; then
    echo "✅ Cert already exists: $crt"
    return
  fi

  # SubjectAltName is important for modern TLS
  $SUDO openssl req -x509 -nodes -newkey rsa:2048 \
    -keyout "$key" \
    -out "$crt" \
    -days 365 \
    -subj "/CN=$domain" \
    -addext "subjectAltName=DNS:$domain"

  $SUDO chmod 600 "$key"
}

write_nginx_config() {
  local domain="$1"
  local ip="$2"
  local flask_port="$3"
  local cert_dir="$4"
  local site_name="$5"

  need_root

  local key="$cert_dir/${domain}.key"
  local crt="$cert_dir/${domain}.crt"

  local conf_path=""
  if [ -d /etc/nginx/sites-available ]; then
    conf_path="/etc/nginx/sites-available/${site_name}.conf"
  else
    conf_path="/etc/nginx/conf.d/${site_name}.conf"
  fi

  echo "🧩 Writing nginx config: $conf_path"

  $SUDO tee "$conf_path" >/dev/null <<EOF
# Auto-generated dev config for WebAuthn testing
# Domain: ${domain}
# Local IP: ${ip}

server {
  listen 443 ssl;
  server_name ${domain};

  ssl_certificate     ${crt};
  ssl_certificate_key ${key};

  # Reasonable dev TLS settings
  ssl_protocols TLSv1.2 TLSv1.3;
  ssl_prefer_server_ciphers off;

  client_max_body_size 25m;

  location / {
    proxy_pass http://127.0.0.1:${flask_port};
    proxy_set_header Host \$host;
    proxy_set_header X-Real-IP \$remote_addr;
    proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto https;

    # WebSockets (if you ever use them)
    proxy_http_version 1.1;
    proxy_set_header Upgrade \$http_upgrade;
    proxy_set_header Connection "upgrade";
  }
}

# Optional HTTP -> HTTPS redirect
server {
  listen 80;
  server_name ${domain};
  return 301 https://\$host\$request_uri;
}
EOF

  # Enable site on Debian-style layouts
  if [ -d /etc/nginx/sites-enabled ] && [ -d /etc/nginx/sites-available ]; then
    $SUDO ln -sf "$conf_path" "/etc/nginx/sites-enabled/${site_name}.conf"
  fi

  # Basic syntax check
  $SUDO nginx -t
}

reload_nginx() {
  need_root

  if command -v systemctl >/dev/null 2>&1; then
    $SUDO systemctl enable nginx >/dev/null 2>&1 || true
    $SUDO systemctl restart nginx
  else
    # macOS Homebrew nginx, etc.
    $SUDO nginx -s reload 2>/dev/null || $SUDO nginx
  fi

  echo "✅ nginx reloaded"
}

if [ "$DEV_MODE" = "1" ]; then
  echo "=== DEV_MODE enabled: configuring nginx + hosts + TLS for WebAuthn ==="

  RP_ID="$(get_rp_id | tr -d '\r\n' || true)"
  if [ -z "$RP_ID" ]; then
    echo "❌ Could not resolve WEBAUTHN_RP_ID. Set it in env: WEBAUTHN_RP_ID=your.local.domain"
    exit 1
  fi

  LOCAL_IP="$(get_local_ip | tr -d '\r\n' || true)"
  if [ -z "$LOCAL_IP" ]; then
    echo "❌ Could not resolve a non-loopback local IP."
    exit 1
  fi

  need_root
  install_nginx
  add_hosts_entry "$RP_ID" "$LOCAL_IP"
  make_self_signed_cert "$RP_ID" "$CERT_DIR"
  write_nginx_config "$RP_ID" "$LOCAL_IP" "$FLASK_PORT" "$CERT_DIR" "$NGINX_SITE_NAME"
  reload_nginx

  echo ""
  echo "✅ Dev WebAuthn endpoint should be available at:"
  echo "   https://${RP_ID}/"
  echo ""
  echo "Note: your browser will warn about the self-signed cert. You must accept it for dev."
fi

# (the rest of your deploy script continues here)
