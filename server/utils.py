import re
import unicodedata
from config import Config
import blake3
import os
import json
import time

def sanitize_for_output(s: str) -> str:
    # mapping for characters we must always escape (use JSON-compatible escapes)
    forced_map = {
        '"': r'\"',          # standard JSON double-quote escape
        '\\': r'\\',         # backslash
        '/': r'\/',          # forward slash
        '<': r'\u003C',      # unicode escape for '<'
        '>': r'\u003E',      # unicode escape for '>'
        "'": r'\u0027',      # unicode escape for single-quote
    }

    parts = []
    # We'll use json.dumps on single characters for correct control/unicode escaping,
    # except for characters in forced_map which we want to override.
    for ch in s:
        if ch in forced_map:
            parts.append(forced_map[ch])
        else:
            # json.dumps on a single-character string returns a quoted JSON string,
            # e.g. json.dumps("\n") -> '"\n"' and json.dumps("é", ensure_ascii=True) -> '"\u00e9"'
            dumped = json.dumps(ch, ensure_ascii=True)
            parts.append(dumped[1:-1])  # strip surrounding quotes

    return ''.join(parts)

def _sanitize_recursive(obj):
    """Recursively sanitize all strings in dicts/lists/tuples."""
    if isinstance(obj, str):
        return sanitize_for_output(obj)
    elif isinstance(obj, dict):
        return {k: _sanitize_recursive(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_sanitize_recursive(v) for v in obj]
    elif isinstance(obj, tuple):
        return tuple(_sanitize_recursive(v) for v in obj)
    else:
        return obj

LENGTH_KEY = 16

def profile(func, *args, **kwargs):
    import inspect
    start = time.perf_counter()

    result = func(*args, **kwargs)

    end = time.perf_counter()
    elapsed_ms = (end - start) * 1000
    caller = inspect.stack()[1]
    print(f"{caller.function}.{func.__name__} took {elapsed_ms:.3f} ms")

    return result

def generate_urls(app):
    """Generate templates/urls.html containing JS window variables for each route."""
    script_lines = ["<script>"]

    for rule in app.url_map.iter_rules():
        if 'static' in rule.endpoint:
            continue  # skip static routes

        func_name = rule.endpoint  # e.g. "main.index" or "index"
        parts = func_name.split(".")
        short_name = parts[-1]  # remove blueprint prefix if any
        dummy_args = {}
        for arg in rule.arguments:
            dummy_args[arg] = f"<{arg}>"
        # Make sure the URL is rendered safely as a Jinja expression
        last_part = "API"
        if func_name.startswith("html"):
            last_part = "HTML"
        elif func_name.startswith("sudo"):
            last_part = "SUDO"
        args_str = ", ".join([f"{arg}='0'" for arg in rule.arguments])
        if args_str:
            js_line = (
                f'window.{short_name}_{last_part} = "{{{{ url_for(\'{func_name}\', {args_str}) }}}}";'
            )
        else:
            js_line = (
                f'window.{short_name}_{last_part} = "{{{{ url_for(\'{func_name}\') }}}}";'
            )
        script_lines.append(js_line)

    script_lines.append("</script>")

    # Write to templates/urls.html
    os.makedirs("templates", exist_ok=True)
    with open("templates/urls.html", "w", encoding="utf-8") as f:
        f.write("\n".join(script_lines))

    print("✅ templates/urls.html generated.")

def gen_key(path, method):
    key = method.encode()
    key += Config.get_key_separator()
    key += path.encode()
    return blake3.blake3(key).hexdigest()[:LENGTH_KEY]

def normalize_email(email: str) -> str:
    email = email.strip().lower()
    local, domain = email.split("@", 1)

    # Handle Gmail & Google Workspace
    if domain in ("gmail.com", "googlemail.com"):
        local = local.split("+", 1)[0].replace(".", "")
        domain = "gmail.com"

    # Handle Outlook / Hotmail / Live
    elif domain in ("outlook.com", "hotmail.com", "live.com"):
        local = local.split("+", 1)[0]

    # Handle iCloud
    elif domain == "icloud.com":
        local = local.split("+", 1)[0]

    # Universal lowercasing + trim
    return f"{local}@{domain}"

def sanitize_email(email: str) -> str:
    """Validate email format."""
    if not isinstance(email, str):
        raise ValueError("Email must be a string.")
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        raise ValueError("Invalid email format.")
    email_split = email.split("@")
    email = sanitize(email_split[0]) + "@" + sanitize(email_split[1])
    return normalize_email(email)

def sanitize(text: str) -> str:
    """
    Sanitizes a string so it only contains characters allowed in email addresses.
    Any disallowed character is replaced with an underscore (_).

    Allowed characters:
      - Letters (A–Z, a–z)
      - Digits (0–9)
      - Dots (.)
      - Underscores (_)
      - Hyphens (-)
      - Plus signs (+)
      - At symbol (@)

    Leading/trailing spaces are removed, Unicode normalized (NFC).
    """
    if not isinstance(text, str):
        raise ValueError("Input must be a string.")

    text = unicodedata.normalize("NFC", text).strip()

    # Replace all disallowed characters with underscores
    sanitized = re.sub(r"[^A-Za-z0-9._+\-@]", "_", text)

    # Collapse multiple consecutive underscores into one for neatness
    sanitized = re.sub(r"_+", "_", sanitized)

    return sanitized


def check_password_complexity(password: str) -> tuple[bool, list[str]]:
    """
    Checks password complexity and returns (is_valid, error_messages).
    Rules:
      - At least 8 characters
      - Contains at least one lowercase letter
      - Contains at least one uppercase letter
      - Contains at least one digit
      - Contains at least one special character
      - No spaces
    """
    errors = []

    if len(password) < 8:
        errors.append("Password must be at least 8 characters long.")
    if not re.search(r"[a-z]", password):
        errors.append("Password must contain at least one lowercase letter.")
    if not re.search(r"[A-Z]", password):
        errors.append("Password must contain at least one uppercase letter.")
    if not re.search(r"\d", password):
        errors.append("Password must contain at least one digit.")
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>_\-+=/\\[\]~`';]", password):
        errors.append("Password must contain at least one special character.")
    if re.search(r"\s", password):
        errors.append("Password cannot contain spaces.")

    return (len(errors) == 0, errors)

def sanitize_username(username: str, min_len: int = 3, max_len: int = 32) -> str:
    """
    Sanitizes and validates a username:
      - Converts to lowercase
      - Removes diacritics (é → e, ñ → n)
      - Allows only [a-z0-9_-]
      - No spaces or special chars
      - Raises ValueError if invalid or length out of bounds
    """
    if not username or not isinstance(username, str):
        raise ValueError("Username must be a non-empty string.")

    # Normalize accents and lowercase
    username = username.strip().lower()
    s_username = unicodedata.normalize('NFKD', username.strip().lower())
    s_username = ''.join(c for c in s_username if not unicodedata.combining(c))
    if s_username != username:
        raise ValueError("Username may only use latin non-diacritical letters or spaces.")
    # Validate allowed pattern
    if not re.fullmatch(r"[a-z0-9_-]+", username):
        raise ValueError("Username may only contain lowercase letters, digits, underscores, or dashes.")
    # Length check
    if not (min_len <= len(username) <= max_len):
        raise ValueError(f"Username must be between {min_len} and {max_len} characters long.")

    return username

# utils_uploads.py
import os
import uuid
from werkzeug.utils import secure_filename
from flask import current_app

def allowed_file(filename: str) -> bool:
    if "." not in filename:
        return False
    ext = filename.rsplit(".", 1)[1].lower()
    return ext in current_app.config.get("ALLOWED_IMAGE_EXTENSIONS", set())

def save_product_image(file_storage) -> str | None:
    """Save an uploaded image under static/uploads and return the relative path."""
    if not file_storage or file_storage.filename == "":
        return None

    if not allowed_file(file_storage.filename):
        raise ValueError("Unsupported file type")

    filename = secure_filename(file_storage.filename)
    ext = filename.rsplit(".", 1)[1].lower()
    new_name = f"{uuid.uuid4().hex}.{ext}"

    upload_folder = current_app.config["UPLOAD_FOLDER"]
    os.makedirs(upload_folder, exist_ok=True)
    full_path = os.path.join(upload_folder, new_name)
    file_storage.save(full_path)

    # Path relative to static/ so you can use url_for("static", filename=image_path)
    return f"uploads/{new_name}"
