import importlib
import logging
import pkgutil
import re

from flask import Blueprint, g, jsonify, request, url_for, redirect, current_app
from flask_jwt_extended import JWTManager, get_jwt, jwt_required
from flask_wtf.csrf import generate_csrf
from sqlalchemy.orm import Session
from werkzeug.exceptions import BadRequest
from datetime import datetime, timezone
from models.db import get_session
from models.log import Log
from models.user import User
from models.user_session import UserSession
from utils import gen_key

logger = logging.getLogger(__name__)

jwt = JWTManager()


def register_blueprints_from_package(app, package, base_blueprint: Blueprint, before_request_fns=None):
    if before_request_fns is None:
        before_request_fns = []

    package_name = package.__name__
    package_path = package.__path__


    for _, module_name, is_pkg in pkgutil.iter_modules(package_path):
        if is_pkg:
            logger.debug("Skipping package module '%s.%s'", package_name, module_name)
            continue

        module_full_name = f"{package_name}.{module_name}"
        module = importlib.import_module(module_full_name)

        if hasattr(module, "bp"):
            sub_bp = getattr(module, "bp")

            for before_request_fn in before_request_fns:
                sub_bp.before_request(before_request_fn)

            sub_bp.after_request(log_if_necessary)
            base_blueprint.register_blueprint(sub_bp)

    app.register_blueprint(base_blueprint)


    for rule in app.url_map.iter_rules():
        if rule.rule.startswith(base_blueprint.url_prefix):
            methods = ",".join(sorted(rule.methods))
            logger.debug("Mounted route %s [%s]", rule.rule, methods)


def is_valid_url_chars(url: str) -> bool:
    pattern = r"""
        ^(
            [A-Za-z0-9\-._~:/?#\[\]@!$&'()*+,;=%]
            |
            <[A-Za-z_][A-Za-z0-9_]*(?::[A-Za-z_][A-Za-z0-9_]*)?>
        )*$"""
    return re.fullmatch(pattern, url, re.VERBOSE) is not None


@jwt_required()
def sudo_validator():
    claims = get_jwt()
    user_obj = User.by_id(claims.get("sub", None))
    if user_obj is None:
        return jsonify({
            "result": "error",
            "message": "user_not_found",
        }), 404

    if not claims.get("sudo", False):
        sudo_required = user_obj.twofa_enabled
        token_obj = UserSession.by_id(claims.get("id", None))

        if not sudo_required:
            if token_obj is not None:
                token_obj.elevate()
            return redirect(url_for("html_pages.admin.admin_elevate"))

        return jsonify({
            "result": "error",
            "message": "sudo_required",
            "hint": "Sudo privileges required. Re-authenticate with your sudo token or request elevated access.",
        }), 401


def log_if_necessary(response):
    try:
        user = get_jwt().get("sub", None)
    except Exception:
        user = None

    if response.status_code >= 400 and response.status_code != 401:
        new_log = Log(
            path=request.path,
            method=request.method,
            response=response.get_data(as_text=True),
            response_code=response.status_code,
            user_id=user,
        )


    return response


def request_validator():
    allowed = {"OPTIONS", "GET", "POST", "PUT", "PATCH", "DELETE"}
    method = request.method.upper()
    path = request.url_rule.rule if request.url_rule else "<unknown>"
    logger.debug("request_validator: method=%s path=%s", method, path)

    if method not in allowed:
        logger.debug("request_validator: disallowed_method method=%s", method)
        return jsonify({
            "result": "error",
            "message": "invalid_method",
            "hint": f"Method '{method}' is not allowed. Use one of {sorted(allowed)}.",
        }), 405

    if method in {"POST", "PUT", "PATCH"}:
        content_type = request.headers.get("Content-Type", "")
        logger.debug("request_validator: content_type=%s", content_type)
        if content_type != "application/json":
            return jsonify({
                "result": "error",
                "message": "invalid_content_type",
                "hint": "Only 'application/json' content type is allowed for POST, PUT, and PATCH requests.",
            }), 415
        try:
            request.get_json(force=True)
            logger.debug("request_validator: JSON body parsed successfully")
        except BadRequest:
            logger.debug("request_validator: invalid_json_body")
            return jsonify({
                "result": "error",
                "message": "invalid_json",
                "hint": "Malformed JSON body. Check your syntax and try again.",
            }), 400

    if method == "OPTIONS":
        has_args = bool(request.args)
        has_body = bool(request.get_data())
        logger.debug("request_validator: options has_args=%s has_body=%s", has_args, has_body)
        if has_args or has_body:
            return jsonify({
                "result": "error",
                "message": "invalid_options_request",
                "hint": "OPTIONS requests must not contain query parameters or a request body.",
            }), 400

    if method == "GET" and request.args:
        logger.debug("request_validator: get_with_query params_count=%d", len(request.args))
        return jsonify({
            "result": "error",
            "message": "invalid_query_params",
            "hint": "GET requests must not contain query parameters for this endpoint.",
        }), 400

    if not is_valid_url_chars(path):
        logger.debug("request_validator: invalid_url_chars path=%s", path)
        return jsonify({
            "result": "error",
            "message": "invalid_url",
            "hint": "URL contains invalid or unsafe characters. Verify your route definition.",
        }), 400

    g.csrf_token = generate_csrf()
    logger.debug("request_validator: csrf_token_issued")
    return None

@jwt_required()
def check_expired():
    claims = get_jwt()
    now = int(datetime.now(timezone.utc).timestamp())
    vu = int(claims["exp"])
    if now > vu:
        return jsonify({
            "result": "error",
            "message": "access_token_expired",
            "hint": "The access token provided has expired. Request a new access token by using your refresh token and the endpoint " + url_for("anon_api.login.refresh") + ".",
        }), 401
    this_session = UserSession.by_id(claims.get("id"))
    if this_session is None or not this_session.is_valid():
        return jsonify({
        "result": "error",
        "message": "access_token_expired",
        "hint": "The access token provided has expired. Request a new access token by using your refresh token and the endpoint " + url_for("anon_api.login.refresh") + ".",
    }), 401


@jwt_required()
def enforce_rbac():
    path = request.url_rule.rule
    method = request.method
    key = gen_key(path, method)
    action_keys = get_jwt().get("perms", [])

    if key not in action_keys:
        print(f"Permission not granted path = {path}")
        return jsonify({
            "result": "error",
            "message": "permission_not_granted",
            "hint": "The permission for the requested action has not been granted. Request the role with the permission to an administrator.",
        }), 401