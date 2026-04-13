# models/module.py
from __future__ import annotations

import logging
from typing import Any, Optional

from sqlalchemy import Integer, String, Text, JSON, select
from sqlalchemy.orm import Mapped, mapped_column, Session

from models.basemodel import Base
from models.agent import Agent
import traceback

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
        print(f"Processing value {value} expected type {type_name} type {type(value)}")
        if value == "null":
            return "null"
        if type(value) == int:
            return value
        if type_name == "hex":
            return int(value, base=16)
        if type_name == "bytes":
            print("Is bytes")
            if type(value) == bytearray:
                return bytes(value)
            if type(value) == bytes:
                return value
            else:
                return value.encode()
        return target_type(value)
    except (ValueError, TypeError) as e:
        logger.error(
            "Exception with value=%r, type=%r, type_name=%r, exception=%s",
            value,
            type(value),
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
            #logger.info("Loading dependency %s into %s", dependency, self.id)

            dep_module = Module.by_id(dependency)
            if dep_module is None:
                logger.error("Missing dependency %s", dependency)
                raise ValueError(f"Missing dependency {dependency}")

            namespace[dependency] = dep_module.exec

        return namespace

    def exec(self, agent_id, args: list[Any]) -> str:
        try:
            print(f"About to execute {self.id}")
            expected_params = self.params or []


            casted_args = []
            #print(expected_params)
            #print(args)
            for i in range(len(expected_params)):
                #print(expected_params[i])
                #print(len(expected_params))
                #print(f"i = {i}")
                #print(f"Length of args {len(args)}")
                if i >= len(args):
                    if expected_params[i].get("optional", False):
                        #print(f"Setting optional parameter {expected_params[i]}")
                        arg = expected_params[i].get("default")
                        casted_arg = try_cast_dynamic(arg, expected_params[i]["type"])
                        casted_args.append(casted_arg)
                    else:
                        return self.get_module_help()
                else:
                    casted_arg = try_cast_dynamic(args[i], expected_params[i]["type"])
                    casted_args.append(casted_arg)
                    
                    
            if len(casted_args) != len(expected_params):
                return self.get_module_help()

            namespace = self.prepare_namespace()
            exec(self.code, namespace)

            func = namespace.get("function")
            if func is None:
                raise ValueError(f"Module {self.id} did not define 'function'")
            retvals = func(agent_id, casted_args)
            agent_obj = Agent.by_id(agent_id)
            if agent_obj.last_executed == self.id:
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
            else:
                retmsg = retvals
        except Exception as e:
            import inspect as stack_inspect
            tb = f"Exception in {stack_inspect.stack()[1].function} from {stack_inspect.stack()[2].function}\n"
            tb = tb + f"Module name = {self.id}\n"
            tb = tb + traceback.format_exc()

            return tb
        return retmsg

    @classmethod
    def get_help(cls) -> str:
        helpmsg = "Available modules:\n"
        modules = cls.all()
        for module in modules:
            helpmsg += module.get_module_help()
        return helpmsg