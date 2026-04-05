from __future__ import annotations

import os
import re
import tempfile

from flask import Blueprint, current_app, jsonify, request

bp = Blueprint("config", __name__, url_prefix="/config")


@bp.route("/", methods=["GET"])
def get_config():
    out = []
    for k, v in current_app.config.items():
        out.append({
            "k": k,
            "v": str(v),
            "type": type(v).__name__,
        })

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

    return repr(value)


def _python_literal(value):
    return repr(value)


def _persist_config_to_file(prop: str, value, var_type: str):
    config_path = os.path.abspath(
        os.path.join(current_app.root_path, "config.py")
    )

    if not os.path.exists(config_path):
        raise FileNotFoundError(f"config.py not found at {config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        txt = f.read()

    m = re.search(r"(^class\s+Config\s*:\s*$)", txt, flags=re.MULTILINE)
    if not m:
        raise RuntimeError("Could not find `class Config:` in config.py")

    class_start = m.end()
    indent = " " * 4

    literal = _to_python_literal(value, var_type)
    new_line = f"{indent}{prop} = {literal}\n"

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

    m = re.search(r"(^class\s+Config\s*:\s*$)", txt, flags=re.MULTILINE)
    if not m:
        raise RuntimeError("Could not find `class Config:` in config.py")

    class_start = m.end()
    indent = " " * 4
    tail = txt[class_start:]

    stop_m = re.search(r"^(class\s+\w+|def\s+\w+)\b", tail, flags=re.MULTILINE)
    class_body = tail if not stop_m else tail[:stop_m.start()]
    class_rest = "" if not stop_m else tail[stop_m.start():]

    lines = class_body.splitlines(True)

    start_re = re.compile(rf"^{re.escape(indent)}{re.escape(prop)}\s*=\s*.*$")
    start_idx = None
    for i, line in enumerate(lines):
        if start_re.match(line):
            start_idx = i
            break

    if start_idx is None:
        return False

    first_line = lines[start_idx]
    first_line_no_comment = first_line.split("#", 1)[0]

    opens = {"[": "]", "{": "}", "(": ")"}
    open_char = None
    close_char = None

    for oc, cc in opens.items():
        if oc in first_line_no_comment and "=" in first_line_no_comment:
            if re.search(rf"=\s*{re.escape(oc)}\s*$", first_line_no_comment.strip()):
                open_char, close_char = oc, cc
                break

    end_idx = start_idx

    if open_char and close_char:
        depth = 0
        for j in range(start_idx, len(lines)):
            chunk = lines[j].split("#", 1)[0]
            depth += chunk.count(open_char)
            depth -= chunk.count(close_char)
            end_idx = j
            if depth <= 0:
                break
    else:
        end_idx = start_idx

    del lines[start_idx:end_idx + 1]

    new_class_body = "".join(lines)
    new_tail = new_class_body + class_rest
    new_txt = txt[:class_start] + new_tail

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

    return True


@bp.route("/", methods=["PATCH"])
def patch_config():
    payload = request.get_json(silent=True) or {}

    required = ["k", "v", "type", "persist"]
    if not all(field in payload for field in required):
        return jsonify({"result": "error", "message": "Missing fields (k, v, type, persist)"}), 400

    prop = str(payload.get("k") or "").strip()
    if not prop:
        return jsonify({"result": "error", "message": "Missing `k` (property name)"}), 400

    value = payload.get("v")
    var_type = str(payload.get("type") or "").strip().lower()
    persist = bool(payload.get("persist", False))

    current_app.config[prop] = value

    if persist:
        try:
            _persist_config_to_file(prop, value, var_type)
        except Exception as e:
            return jsonify({
                "result": "error",
                "message": f"Runtime updated, but persist failed: {str(e)}",
            }), 500

    return jsonify({
        "result": "success",
        "message": {
            "k": prop,
            "v": current_app.config.get(prop),
            "type": var_type,
            "persisted": persist,
        },
    }), 200


@bp.route("/delete", methods=["PATCH"])
def delete_config():
    payload = request.get_json(silent=True) or {}

    required = ["k", "persist"]
    if not all(field in payload for field in required):
        return jsonify({"result": "error", "message": "Missing fields (k, persist)"}), 400

    prop = str(payload.get("k") or "").strip()
    if not prop:
        return jsonify({"result": "error", "message": "Missing `k` (property name)"}), 400

    persist = bool(payload.get("persist", False))

    current_app.config.pop(prop, None)

    if persist:
        try:
            delete_config_from_config(prop)
        except Exception as e:
            return jsonify({
                "result": "error",
                "message": f"Runtime updated, but persist failed: {str(e)}",
            }), 500

    return jsonify({
        "result": "success",
        "message": "Property deleted successfully",
    }), 200