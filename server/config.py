import os
import random
import blake3
from datetime import timedelta
import math
import secrets
import string
from collections import Counter
from typing import Mapping, MutableMapping, List, Union

ALPHANUM = string.ascii_letters + string.digits + "+/"


def _shannon_entropy_bits(value: Union[str, bytes]) -> float:
    """
    Compute total Shannon entropy (in bits) of a string or bytes sequence.
    H_total = H_per_symbol * N
    """
    if isinstance(value, bytes):
        seq = list(value)
    else:
        seq = list(value or "")
    n = len(seq)
    if n == 0:
        return 0.0
    counts = Counter(seq)
    H_per_symbol = -sum((c / n) * math.log2(c / n) for c in counts.values())
    return H_per_symbol * n


def _gen_alnum_key(length: int = 32) -> str:
    """Generate a cryptographically strong alphanumeric key with up to +50% random length."""
    max_length = int(length * 1.5)
    real_length = secrets.randbelow(max_length - length + 1) + length
    return "".join(secrets.choice(ALPHANUM) for _ in range(real_length))


def ensure_min_entropy_keys(config: MutableMapping, dev: bool = False) -> List[str]:
    """
    For each config entry whose name ends with 'KEY', check its entropy.
    If entropy < MIN_ENTROPY, generate a new secure 32-char alphanumeric key.

    Prints entropy info before and after rotation.
    If dev=True, also prints the actual key values.

    Returns a list of updated key names.
    """
    min_entropy_bits = (
        config.get("MIN_ENTROPY", 128)
        if isinstance(config, Mapping)
        else getattr(config, "MIN_ENTROPY", 128)
    )

    min_size_key = (
        config.get("MIN_KEY_LENGTH", 32)
        if isinstance(config, Mapping)
        else getattr(config, "MIN_KEY_LENGTH", 32)
    )

    renew_anyways = config.get("ENV") != "development" and not config.get("ALLOW_NON_RANDOM_PROD_KEYS")

    updated: List[str] = []
    items = list(getattr(config, "items")())

    # With Base64 characters you can get a theoretical maximum of 6 bits/symbol
    # Will give 5% margin to avoid endless computation for keys.
    max_theoretical_entropy = float(6 * min_size_key)
    if float(min_entropy_bits) > float(max_theoretical_entropy) * 0.95:
        raise ValueError("MIN_ENTROPY exceeds maximum theoretical value. Increase key size or reduce minimum entropy.")

    for name, value in items:
        if not isinstance(name, str) or not name.endswith("KEY"):
            continue
        if not isinstance(value, (str, bytes)):
            continue
        old_entropy = _shannon_entropy_bits(value)
        if renew_anyways:
            old_entropy = 0
        if old_entropy < float(min_entropy_bits):
            new_entropy = old_entropy
            while new_entropy < float(min_entropy_bits):
                old_val = value
                new_val = _gen_alnum_key(min_size_key)
                new_entropy = _shannon_entropy_bits(new_val)
            config[name] = new_val
            updated.append(name)

        else:
            new_entropy = old_entropy

    return updated


class Config:
    from deploy import MYSQL_USER, MYSQL_PASSWORD, MYSQL_PORT, MYSQL_DB
    WEBAUTHN_RP_ID = os.environ.get("WEBAUTHN_RP_ID", "guachin.local")
    WEBAUTHN_RP_NAME = os.environ.get("WEBAUTHN_RP_NAME", "GUACHIN")

    WEBAUTHN_RP_ENTITY = {
        "id": WEBAUTHN_RP_ID,
        "name": WEBAUTHN_RP_NAME,
    }
    WEBAUTHN_ORIGIN = os.environ.get("WEBAUTHN_ORIGIN")  # set by deploy.py in dev
    WEBAUTHN_RP_ENTITY = os.environ.get("WEBAUTHN_RP_ID", "guachin.local")
    _cached_separator: bytes | None = None  # internal cache


    @staticmethod
    def _derive_seed(secret: str) -> int:
        """Derive a deterministic integer seed from the secret key using BLAKE3."""
        digest = blake3.blake3(secret.encode()).digest(length=8)
        return int.from_bytes(digest, "big")

    @classmethod
    def get_key_separator(cls) -> bytes:
        """Generate a reproducible 16-byte separator from the SECRET_KEY (cached)."""
        if cls._cached_separator is not None:
            return cls._cached_separator

        secret = os.environ.get("SECRET_KEY", "undefined")
        seed = cls._derive_seed(secret)
        rng = random.Random(seed)
        cls._cached_separator = bytes(rng.getrandbits(8) for _ in range(16))
        return cls._cached_separator

    # --- Static configuration ---
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "undefined")
    DOMAIN = "guachin.local"
    SECRET_KEY = "undefined"

    _seed = int.from_bytes(blake3.blake3(SECRET_KEY.encode()).digest(length=8), "big")
    UPLOAD_ROOT = "./modules"
    ENTROPY_THRESHOLD = 5
    KEYS_LENGTH = 48
    JWT_ALGORITHM = "HS256"
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)
    WEBAUTHN_STATE_TIMEOUT = 30
    DEBUG = False
    ENV_TEST_TIMEOUT = 0.5
    MIN_ENTROPY = 180
    MIN_KEY_LENGTH = 32
    ALLOW_NON_RANDOM_PROD_KEYS = False
    # Where product images will be stored (under /static)
    UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), "static", "uploads")
    ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024  # 5 MB
    # Flask-SQLAlchemy compatibility
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_DATABASE_URI = f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@127.0.0.1:{MYSQL_PORT}/{MYSQL_DB}"


class DevelopmentConfig(Config):
    JWT_SECRET_KEY = "83oAicwGlmecsCA7b61G3w6vpZGRqH0VD148r2KuLzr"
    JWT_SECRET_SECOND_KEY = "EOygGB4aWphXnL9dnNCzZS7w9u5l4pJQkSI3Q4TS+8B2"
    SECRET_KEY = "pEpwzAV5g9R1gGNVBqTZNmvoZTw5l1+PBLOrh7zj"
    RESET_SECRET_KEY = "EOygGB4aWphXnL9dnNCzZS7w9u5l4pJQkSI3Q4TS"
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=12)
    ENV = "development"
    DEBUG = True
    # You can override with DATABASE_URL="postgresql+psycopg://user:pass@localhost:5432/guachin

class ProductionConfig(Config):
    JWT_SECRET_KEY = "undefined"
    JWT_SECRET_SECOND_KEY = "undefined"
    SECRET_KEY = "undefined"
    RESET_SECRET_KEY = "undefined"
    SESSION_COOKIE_SECURE = True
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=12)
    ENV = "production"
    DEBUG = False
    # In production, DATABASE_URL must be provided via environment
