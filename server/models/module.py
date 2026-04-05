# models/module.py
from __future__ import annotations

import logging
from typing import Any, Optional

from sqlalchemy import Integer, String, Text, JSON, select
from sqlalchemy.orm import Mapped, mapped_column, Session

from models.basemodel import Base

logger = logging.getLogger(__name__)

TYPE_MAP = {
    "hex": int,
    "int": int,
    "float": float,
    "str": str,
    "bool": bool,
    "bytes": bytes,
}


def try_cast_dynamic(value: Any, type_name: str):
    target_type = TYPE_MAP.get(type_name)
    if not target_type:
        return None

    try:
        if type_name == "hex":
            return int(value, base=16)
        if type_name == "bytes":
            return value.encode()
        return target_type(value)
    except (ValueError, TypeError) as e:
        logger.error(
            "Exception with value=%r, type_name=%r, exception=%s",
            value,
            type_name,
            e,
        )
        return None


class Module(Base):
    __tablename__ = "modules"

    id: Mapped[str] = mapped_column(String(255),primary_key=True, unique=True)
    code: Mapped[str] = mapped_column(Text, nullable=False, default="")
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    params: Mapped[Optional[list[dict[str, Any]]]] = mapped_column(JSON)
    dependencies: Mapped[Optional[list[str]]] = mapped_column(JSON)

    def get_module_help(self) -> str:
        helpmsg = f"\t- {self.id}: {self.description}\n"
        for param in self.params or []:
            helpmsg += (
                f"\t\t{param['name']}: {param['description']}. "
                f"Type = {param['type']}\n"
            )
        return helpmsg

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "id": self.id,
            "description": self.description,
            "params": self.params,
            "dependencies": self.dependencies,
        }

    def prepare_namespace(self) -> dict[str, Any]:
        namespace: dict[str, Any] = {}

        for dependency in self.dependencies or []:
            logger.info("Loading dependency %s into %s", dependency, self.id)

            dep_module = Module.by_id(dependency)
            if dep_module is None:
                logger.error("Missing dependency %s", dependency)
                raise ValueError(f"Missing dependency {dependency}")

            dep_namespace = dep_module.prepare_namespace()

            temp_namespace = dict(dep_namespace)
            exec(dep_module.code, temp_namespace)

            func = temp_namespace.get("function")
            if func is None:
                logger.error("Dependency %s did not define 'function'", dependency)
                raise ValueError(f"Dependency {dependency} did not define 'function'")

            namespace |= dep_namespace
            namespace[dependency] = func

        return namespace

    def exec(self, agent_id, args: list[Any]) -> str:
        print(f"About to execute {self.id}")
        expected_params = self.params or []

        if len(args) != len(expected_params):
            return self.get_module_help()

        casted_args = []
        for i in range(len(args)):
            casted_arg = try_cast_dynamic(args[i], expected_params[i]["type"])
            if casted_arg is None:
                logger.error("Invalid argument %r. Param spec: %r", args[i], expected_params[i])
                return self.get_module_help()
            casted_args.append(casted_arg)

        namespace = self.prepare_namespace()
        exec(self.code, namespace)

        func = namespace.get("function")
        if func is None:
            raise ValueError(f"Module {self.id} did not define 'function'")

        retvals = func(agent_id, casted_args)

        retmsg = ""
        for i, (name, value) in enumerate(retvals.items()):
            retmsg += f"{name} = "
            if isinstance(value, int):
                retmsg += hex(value)
            elif isinstance(value, str):
                retmsg += value
            elif isinstance(value, bytes):
                retmsg += value.hex()
            else:
                retmsg += "Unrecognized type"

            if i != len(retvals) - 1:
                retmsg += ", "

        return retmsg

    @classmethod
    def get_help(cls) -> str:
        helpmsg = "Available modules:\n"
        modules = cls.all()
        for module in modules:
            helpmsg += module.get_module_help()
        return helpmsg