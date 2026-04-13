from flask import Blueprint, jsonify, request

from models.module import Module
from models.schema import load_modules_from_directory
bp = Blueprint("modules", __name__, url_prefix="/modules")
import json
import os

def normalize_module_payload(data):
    return {
        "id": data.get("id"),
        "code": data.get("code", ""),
        "description": data.get("description", ""),
        "params": data.get("params", []),
        "dependencies": data.get("dependencies", []),
    }

def write_module(id, description, params, dependencies, code):
    to_write = f"NAME = \"{id}\"\n"
    to_write += f"DESCRIPTION = \"{description}\"\n"
    to_write += f"PARAMS = [{json.dumps(params)}]\n"
    to_write += f"DEPENDENCIES = {json.dumps(dependencies)}\n\n"
    to_write += code
    with open(os.path.join("modules", f"{id}.py"), "w", encoding="utf-8") as f:
        f.write(to_write)


@bp.route("/", methods=["GET"])
def list_modules():
    modules = Module.all()
    return jsonify({
        "result": "success",
        "message": [m.to_dict() for m in modules],
    }), 200


@bp.route("/", methods=["POST"])
def create_module():
    data = request.get_json() or {}
    payload = normalize_module_payload(data)

    id = payload["id"]
    code = payload["code"]
    description = payload["description"]
    params = payload["params"]
    dependencies = payload["dependencies"]

    if not id:
        return jsonify({
            "result": "error",
            "message": "Missing 'id' field",
        }), 400

    if Module.by_id(id):
        return jsonify({
            "result": "error",
            "message": "Module already exists",
        }), 409

    write_module(id, description, params, dependencies, code)
    load_modules_from_directory()
    module_obj = Module.by_id(id)

    if module_obj is not None:
        return jsonify({
            "result": "success",
            "message": "Module created",
            "module": module_obj.to_dict(),
        }), 201
    else:
        return jsonify({
            "result": "error",
            "message": "Error creating new module"
        }), 500


@bp.route("/", methods=["PATCH"])
def update_module():
    data = request.get_json() or {}
    payload = normalize_module_payload(data)

    id = payload["id"]
    code = payload["code"]
    description = payload["description"]
    params = payload["params"]
    dependencies = payload["dependencies"]

    if not id:
        return jsonify({
            "result": "error",
            "message": "Missing 'id' field",
        }), 400

    module_obj = Module.by_id(id)
    if not module_obj:
        return jsonify({
            "result": "error",
            "message": "Module not found",
        }), 404
    if module_obj.default == True:
            return jsonify({
                "result":"error",
                "message":"Cannot modify built-in module"
            }), 401
    write_module(id, description, params, dependencies, code)
    load_modules_from_directory()

    return jsonify({
        "result": "success",
        "message": "Module updated",
        "module": module_obj.to_dict(),
    }), 200


@bp.route("/delete", methods=["POST"])
def delete_module():
    data = request.get_json() or {}
    id = data.get("id")

    if not id:
        return jsonify({
            "result": "error",
            "message": "Missing 'id' field",
        }), 400

    module_obj = Module.by_id(id)
    if not module_obj:
        return jsonify({
            "result": "error",
            "message": "Module not found",
        }), 404
    if module_obj.default == True:
        return jsonify({
            "result":"error",
            "message":"Cannot delete built-in module"
        }), 401
    path = os.path.join("modules", f"{id}.py")
    try:
        os.remove(path)
    except:
        pass
    module_obj.delete()

    return jsonify({
        "result": "success",
        "message": "Module deleted",
    }), 200