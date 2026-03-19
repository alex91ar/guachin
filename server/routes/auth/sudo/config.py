from flask import jsonify, request, current_app, Blueprint
import os
import re
import tempfile

bp = Blueprint("config", __name__, url_prefix='/config')

@bp.route("/", methods=["GET"])
def get_config():
    """
    Returns current_app.config as property/value pairs.
    Non-JSON-serializable values are stringified.
    """
    out = []
    for k, v in current_app.config.items():
        val = dict()
        val["k"] = k
        val["v"] = str(v)
        val["type"] = type(v).__name__
        out.append(val)

    return jsonify({"result": "success", "message": out}), 200

def _to_python_literal(value, var_type: str) -> str:
    var_type = (var_type or "").lower()

    if var_type == "str":
        return repr(str(value))

    if var_type == "int":
        return str(int(value))

    if var_type == "float":
        return str(float(value))

    if var_type == "bool":
        return "True" if bool(value) else "False"

    if var_type == "list":
        return repr(list(value) if isinstance(value, list) else [])

    if var_type == "dict":
        return repr(dict(value) if isinstance(value, dict) else {})

    if var_type in ("none", "null"):
        return "None"

    # fallback (safe, readable)
    return repr(value)


def _python_literal(value):
    """
    Convert incoming JSON value into a Python literal string for config.py.
    """
    # value is already a Python object from request.json
    return repr(value)


def _persist_config_to_file(prop: str, value, var_type: str):
    """
    Modifies config.py Config class:
      - If prop exists in class Config: replace the assignment line
      - If not: insert new assignment within class Config

    var_type: str | int | float | bool | list | dict | none
    """
    import os, re, tempfile
    from flask import current_app

    config_path = os.path.abspath(
        os.path.join(current_app.root_path, "config.py")
    )

    if not os.path.exists(config_path):
        raise FileNotFoundError(f"config.py not found at {config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        txt = f.read()

    # --- find class Config ---
    m = re.search(r"(^class\s+Config\s*:\s*$)", txt, flags=re.MULTILINE)
    if not m:
        raise RuntimeError("Could not find `class Config:` in config.py")

    class_start = m.end()
    indent = " " * 4
    
    # --- convert value to Python literal ---
    literal = _to_python_literal(value, var_type)
    new_line = f"{indent}{prop} = {literal}\n"

    # --- replace or insert ---
    prop_re = re.compile(
        rf"^({re.escape(indent)}{re.escape(prop)}\s*=\s*).*$",
        re.MULTILINE,
    )

    tail = txt[class_start:]
    
    if prop_re.search(tail):
        tail2 = prop_re.sub(new_line.rstrip("\n"), tail, count=1)
        new_txt = txt[:class_start] + tail2
    else:
        tail_lines = tail.splitlines(True)

        i = 0
        while i < len(tail_lines) and tail_lines[i].strip() == "":
            i += 1

        # skip class docstring if present
        if i < len(tail_lines) and tail_lines[i].lstrip().startswith(('"""', "'''")):
            quote = tail_lines[i].lstrip()[:3]
            i += 1
            while i < len(tail_lines):
                if quote in tail_lines[i]:
                    i += 1
                    break
                i += 1

        insertion_index = sum(len(x) for x in tail_lines[:i])
        new_txt = (
            txt[:class_start]
            + tail[:insertion_index]
            + new_line
            + tail[insertion_index:]
        )

    # --- atomic write ---
    dirpath = os.path.dirname(config_path)
    fd, tmp_path = tempfile.mkstemp(prefix="config_", suffix=".py", dir=dirpath)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as tmp:
            tmp.write(new_txt)
        os.replace(tmp_path, config_path)
    except Exception:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass
        raise

def delete_config_from_config(prop: str):
    """
    Removes a config property assignment from config.py's class Config.

    - Deletes a single-line assignment:     PROP = ...
    - Best-effort deletes multi-line assignments that start with:
          PROP = [
          PROP = {
          PROP = (
      by removing until the matching closing bracket/paren at the same indent depth.
    """
    import os, re, tempfile
    from flask import current_app

    prop = (prop or "").strip()
    if not prop:
        raise ValueError("Missing `prop`")

    config_path = os.path.abspath(
        os.path.join(current_app.root_path, "config.py")
    )

    if not os.path.exists(config_path):
        raise FileNotFoundError(f"config.py not found at {config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        txt = f.read()

    # --- find class Config ---
    m = re.search(r"(^class\s+Config\s*:\s*$)", txt, flags=re.MULTILINE)
    if not m:
        raise RuntimeError("Could not find `class Config:` in config.py")

    class_start = m.end()
    indent = " " * 4
    tail = txt[class_start:]

    # Restrict edits to the class body by stopping at next top-level class/def (or EOF)
    stop_m = re.search(r"^(class\s+\w+|def\s+\w+)\b", tail, flags=re.MULTILINE)
    class_body = tail if not stop_m else tail[:stop_m.start()]
    class_rest = "" if not stop_m else tail[stop_m.start():]

    lines = class_body.splitlines(True)

    # Find the start line of the assignment
    # matches: "    PROP = ..."
    start_re = re.compile(rf"^{re.escape(indent)}{re.escape(prop)}\s*=\s*.*$")
    start_idx = None
    for i, line in enumerate(lines):
        if start_re.match(line):
            start_idx = i
            break

    # If it doesn't exist, no-op
    if start_idx is None:
        return False  # deleted = False

    # Determine if multi-line assignment (starts with an opening bracket/paren and not closed on same line)
    first_line = lines[start_idx]
    # Remove comments to avoid bracket confusion
    first_line_no_comment = first_line.split("#", 1)[0]

    opens = {"[": "]", "{": "}", "(": ")"}
    open_char = None
    close_char = None

    for oc, cc in opens.items():
        if oc in first_line_no_comment and "=" in first_line_no_comment:
            # heuristic: consider multi-line only if it looks like "PROP = [" or "PROP = {" or "PROP = ("
            if re.search(rf"=\s*\{re.escape(oc)}\s*$", first_line_no_comment.strip()):
                open_char, close_char = oc, cc
                break

    end_idx = start_idx

    if open_char and close_char:
        # Remove until matching closing bracket/paren is found
        # We'll count bracket depth starting from this line.
        depth = 0
        for j in range(start_idx, len(lines)):
            chunk = lines[j].split("#", 1)[0]  # strip comments
            depth += chunk.count(open_char)
            depth -= chunk.count(close_char)
            end_idx = j
            if depth <= 0:
                break
        # include end_idx line in deletion
    else:
        # single-line assignment
        end_idx = start_idx

    # Delete the block
    del lines[start_idx:end_idx + 1]

    new_class_body = "".join(lines)
    new_tail = new_class_body + class_rest
    new_txt = txt[:class_start] + new_tail

    # --- atomic write ---
    dirpath = os.path.dirname(config_path)
    fd, tmp_path = tempfile.mkstemp(prefix="config_", suffix=".py", dir=dirpath)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as tmp:
            tmp.write(new_txt)
        os.replace(tmp_path, config_path)
    except Exception:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass
        raise

    return True  # deleted = True


@bp.route("/", methods=["PATCH"])
def patch_config():
    """
    Receives JSON: { "k": "...", "v": ..., "type": "...", "persist": true/false }
    Sets current_app.config[k] at runtime.
    If persist=true: also edits config.py Config class to include/replace that property.
    """
    payload = request.get_json(silent=True) or {}

    # required fields for the new frontend shape
    required = ["k", "v", "type", "persist"]
    if not all(field in payload for field in required):
        return jsonify({"result": "error", "message": "Missing fields (k, v, type, persist)"}), 400

    prop = str(payload.get("k") or "").strip()
    if not prop:
        return jsonify({"result": "error", "message": "Missing `k` (property name)"}), 400

    value = payload.get("v")
    var_type = str(payload.get("type") or "").strip().lower()
    persist = bool(payload.get("persist", False))

    # runtime set
    current_app.config[prop] = value

    # persist to config.py if requested
    if persist:
        try:
            _persist_config_to_file(prop, value, var_type)
        except Exception as e:
            return jsonify({
                "result": "error",
                "message": f"Runtime updated, but persist failed: {str(e)}"
            }), 500

    return jsonify({
        "result": "success",
        "message": {
            "k": prop,
            "v": current_app.config.get(prop),
            "type": var_type,
            "persisted": persist
        }
    }), 200

@bp.route("/delete", methods=["PATCH"])
def delete_config():
    """
    Receives JSON: { "k": "...", "v": ..., "type": "...", "persist": true/false }
    Sets current_app.config[k] at runtime.
    If persist=true: also edits config.py Config class to include/replace that property.
    """
    payload = request.get_json(silent=True) or {}

    # required fields for the new frontend shape
    required = ["k", "persist"]
    if not all(field in payload for field in required):
        return jsonify({"result": "error", "message": "Missing fields (k, persist)"}), 400

    prop = str(payload.get("k") or "").strip()
    if not prop:
        return jsonify({"result": "error", "message": "Missing `k` (property name)"}), 400

    persist = bool(payload.get("persist", False))

    # runtime set
    current_app.config.pop(prop, None)

    # persist to config.py if requested
    if persist:
        try:
            delete_config_from_config(prop)
        except Exception as e:
            return jsonify({
                "result": "error",
                "message": f"Runtime updated, but persist failed: {str(e)}"
            }), 500

    return jsonify({
        "result": "success",
        "message": "Property deleted successfully"
    }), 200