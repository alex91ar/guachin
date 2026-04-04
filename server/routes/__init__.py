import importlib
import pkgutil
import logging
import re
import json
from flask import Blueprint, request, g, jsonify, url_for, redirect
from flask_jwt_extended import jwt_required, get_jwt, get_jwt_identity, JWTManager
from flask_wtf.csrf import generate_csrf
from werkzeug.exceptions import BadRequest
from utils import gen_key
from models.user_session import UserSession
from models.user import User
from models.log import Log
from routes.anon.auth import get_raw_token

logger = logging.getLogger(__name__)

jwt = JWTManager()


def register_blueprints_from_package(app, package, base_blueprint: Blueprint, before_request_fns=[]):
    package_name = package.__name__
    package_path = package.__path__

    logger.info(
        "Registering blueprints from package '%s' under base blueprint '%s'",
        package_name, base_blueprint.name
    )

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
                logger.info(
                    "Attached before_request '%s' to '%s.%s'",
                    getattr(before_request_fn, "__name__", str(before_request_fn)),
                    module_full_name, getattr(sub_bp, "name", "<unnamed>")
                )

            base_blueprint.register_blueprint(sub_bp)
        else:
            logger.info("Module '%s' has no 'bp'; skipped", module_full_name)

    app.register_blueprint(base_blueprint)

    logger.info(
        "Mounted base blueprint '%s' at prefix '%s'",
        base_blueprint.name, base_blueprint.url_prefix
    )

    logger.info("Enumerating routes for base blueprint '%s'", base_blueprint.name)
    for rule in app.url_map.iter_rules():
        if rule.rule.startswith(base_blueprint.url_prefix):
            methods = ",".join(sorted(rule.methods))



def is_valid_url_chars(url: str) -> bool:
    """
    Validates that a Flask URL rule contains only safe URL characters
    and valid Flask-style parameters (e.g. <int:id>, <string:name>, <uuid:uid>, <id>).
    """
    pattern = r"""
        ^(
            [A-Za-z0-9\-._~:/?#\[\]@!$&'()*+,;=%]              # normal chars
            |                                                 # or
            <[A-Za-z_][A-Za-z0-9_]*(?::[A-Za-z_][A-Za-z0-9_]*)?>  # <name> or <converter:name>
        )*$"""
    return re.fullmatch(pattern, url, re.VERBOSE) is not None


@jwt_required()
def sudo_validator():
    claims = get_jwt()
    user_obj = User.by_id(claims.get("sub",None))
    if not claims.get("sudo", False):
        sudo_required = user_obj.twofa_enabled
        if not sudo_required:
            UserSession.by_id(claims.get("id", None)).elevate()
            return redirect(url_for('html_pages.admin.admin_elevate'))
        else:
            return jsonify({
                "result": "error",
                "message": "sudo_required",
                "hint": "Sudo privileges required. Re-authenticate with your sudo token or request elevated access."
            }), 401


def log_if_necessary(response):
    try:
        user = get_jwt().get("sub", None)
    except:
        user = None
    if response.status_code >= 400 and response.status_code != 401:
        new_log = Log(path=request.path, method=request.method, response=response.get_data(as_text=True), response_code=response.status_code, user_id=user)
        new_log.save()
    return response

def request_validator():
    allowed = {'OPTIONS', 'GET', 'POST', 'PUT', 'PATCH', 'DELETE'}
    method = request.method.upper()
    path = request.url_rule.rule if request.url_rule else "<unknown>"
    logger.debug("request_validator: method=%s path=%s", method, path)

    # 1️⃣ Enforce allowed HTTP methods
    if method not in allowed:
        logger.debug("request_validator: disallowed_method method=%s", method)
        return jsonify({
            "result": "error",
            "message": "invalid_method",
            "hint": f"Method '{method}' is not allowed. Use one of {sorted(allowed)}."
        }), 405

    # 2️⃣ Enforce JSON for write operations
    if method in {'POST', 'PUT', 'PATCH'}:
        content_type = request.headers.get('Content-Type', '')
        logger.debug("request_validator: content_type=%s", content_type)
        if content_type != 'application/json':
            return jsonify({
                "result": "error",
                "message": "invalid_content_type",
                "hint": "Only 'application/json' content type is allowed for POST, PUT, and PATCH requests."
            }), 415
        try:
            request.get_json(force=True)
            logger.debug("request_validator: JSON body parsed successfully")
        except BadRequest:
            logger.debug("request_validator: invalid_json_body")
            return jsonify({
                "result": "error",
                "message": "invalid_json",
                "hint": "Malformed JSON body. Check your syntax and try again."
            }), 400

    # 3️⃣ OPTIONS must not have query or body
    if method == 'OPTIONS':
        has_args = bool(request.args)
        has_body = bool(request.get_data())
        logger.debug("request_validator: options has_args=%s has_body=%s", has_args, has_body)
        if has_args or has_body:
            return jsonify({
                "result": "error",
                "message": "invalid_options_request",
                "hint": "OPTIONS requests must not contain query parameters or a request body."
            }), 400

    # 4️⃣ GET should not have query parameters (if this is intended)
    if method == 'GET' and request.args:
        logger.debug("request_validator: get_with_query params_count=%d", len(request.args))
        return jsonify({
            "result": "error",
            "message": "invalid_query_params",
            "hint": "GET requests must not contain query parameters for this endpoint."
        }), 400

    # 5️⃣ URL validation
    if not is_valid_url_chars(path):
        logger.debug("request_validator: invalid_url_chars path=%s", path)
        return jsonify({
            "result": "error",
            "message": "invalid_url",
            "hint": "URL contains invalid or unsafe characters. Verify your route definition."
        }), 400

    g.csrf_token = generate_csrf()
    logger.debug("request_validator: csrf_token_issued")
    return None  # valid request

@jwt.expired_token_loader
def expired_token_callback(jwt_header, jwt_payload):
    return jsonify({
        "result": "error",
        "message": "access_token_expired"
    }), 401

@jwt_required()
def check_expired():
    claims = get_jwt()
    token_obj = UserSession.by_id(claims.get("id", None))
    if not token_obj or not token_obj.is_valid():
        return jsonify({
            "result": "error",
            "message": "access_token_expired",
            "hint": "The access token provided has expired. Request a new access token by using your refresh token and the endpoint " + url_for('anon_api.login.refresh') + "."
        }), 401



@jwt_required()
def enforce_rbac():
    path = request.url_rule.rule
    method = request.method
    key = gen_key(path, method)
    action_keys = get_jwt().get("perms", [])
    #logger.info(
    #    "enforce_rbac: user=%s path=%s method=%s generated_key=%s user_perms_count=%d",
    #    get_jwt().get("sub"), path, method, key, len(action_keys)
    #)
    if key not in action_keys:
        logger.info("enforce_rbac: permission_denied key_missing_in_claims")
        return jsonify({
            "result": "error",
            "message": "permission_not_granted",
            "hint": "The permission for the requested action has not been granted. Request the role with the permission to an administrator."
        }), 401
