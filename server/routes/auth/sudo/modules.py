# routes/auth/sudo/module.py

from flask import Blueprint, jsonify, request

from models.module import Module

bp = Blueprint("modules", __name__, url_prefix="/modules")


def normalize_module_payload(data):
    return {
        "name": data.get("name"),
        "code": data.get("code", ""),
        "description": data.get("description", ""),
        "params": data.get("params", []),
        "dependencies": data.get("dependencies", []),
    }


# --------------------- GET all modules --------------------- #
@bp.route("/", methods=["GET"])
def list_modules():
    """List all modules."""
    try:
        modules = Module.all()
        return jsonify({
            "result": "success",
            "message": [m.to_dict() for m in modules]
        }), 200
    except Exception as e:
        return jsonify({
            "result": "error",
            "message": str(e)
        }), 500


# --------------------- CREATE module --------------------- #
@bp.route("/", methods=["POST"])
def create_module():
    """Create a new module."""
    data = request.get_json() or {}
    payload = normalize_module_payload(data)

    name = payload["name"]
    code = payload["code"]
    description = payload["description"]
    params = payload["params"]
    dependencies = payload["dependencies"]

    if not name:
        return jsonify({
            "result": "error",
            "message": "Missing 'name' field"
        }), 400

    try:
        if Module.get(name):
            return jsonify({
                "result": "error",
                "message": "Module already exists"
            }), 409

        module_obj = Module(
            name=name,
            code=code,
            description=description,
            params=params,
            dependencies=dependencies
        )
        module_obj.save()

        return jsonify({
            "result": "success",
            "message": "Module created",
            "module": module_obj.to_dict()
        }), 201

    except Exception as e:
        return jsonify({
            "result": "error",
            "message": str(e)
        }), 500


# --------------------- UPDATE module --------------------- #
@bp.route("/", methods=["PATCH"])
def update_module():
    """Update an existing module."""
    data = request.get_json() or {}
    payload = normalize_module_payload(data)

    name = payload["name"]
    code = payload["code"]
    description = payload["description"]
    params = payload["params"]
    dependencies = payload["dependencies"]

    if not name:
        return jsonify({
            "result": "error",
            "message": "Missing 'name' field"
        }), 400

    try:
        module_obj = Module.get(name)
        if not module_obj:
            return jsonify({
                "result": "error",
                "message": "Module not found"
            }), 404

        module_obj.code = code
        module_obj.description = description
        module_obj.params = params
        module_obj.dependencies = dependencies
        module_obj.save()

        return jsonify({
            "result": "success",
            "message": "Module updated",
            "module": module_obj.to_dict()
        }), 200

    except Exception as e:
        return jsonify({
            "result": "error",
            "message": str(e)
        }), 500


# --------------------- DELETE module --------------------- #
@bp.route("/delete", methods=["POST"])
def delete_module():
    """Delete a module by name."""
    data = request.get_json() or {}
    name = data.get("name")

    if not name:
        return jsonify({
            "result": "error",
            "message": "Missing 'name' field"
        }), 400

    try:
        module_obj = Module.get(name)
        if not module_obj:
            return jsonify({
                "result": "error",
                "message": "Module not found"
            }), 404

        module_obj.delete()

        return jsonify({
            "result": "success",
            "message": "Module deleted"
        }), 200

    except Exception as e:
        return jsonify({
            "result": "error",
            "message": str(e)
        }), 500