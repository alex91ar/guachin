from models.basemodel import Base, db
from models.db import get_session
from sqlalchemy import select
import logging
logger = logging.getLogger(__name__)

TYPE_MAP = {
    "hex": int,
    "int": int,
    "float": float,
    "str": str,
    "bool": bool,
    "bytes": bytes,
}

def try_cast_dynamic(value, type_name):
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
        logger.error(f"Exception with value = {value}, type_name = {type_name}, exception = {e}")
        return None

class Module(Base):
    __tablename__ = "modules"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.Text, nullable=False, default="")
    name = db.Column(db.String(255), unique=True)
    description = db.Column(db.Text, nullable =False, default="")
    params = db.Column(db.JSON)
    dependencies = db.Column(db.JSON)
    def get_module_help(self):
        helpmsg = f"\t- {self.name}: {self.description}\n"
        for param in self.params:
            helpmsg += f"\t\t{param["name"]}: {param["description"]}. Type = {param["type"]}\n"
        return helpmsg

    def exec(self, agent_id, args):
        if len(args) != len(self.params):
            return self.get_module_help()
        casted_args = []
        for i in range(len(args)):
            casted_arg = try_cast_dynamic(args[i], self.params[i]["type"])
            if casted_arg is None:
                logger.error(f"Invalid argument {args[i]}. {self.params[i]}")
                return self.get_module_help()
            casted_args.append(casted_arg)

        namespace = {}
        dependencies = []
        for dependency in self.dependencies:
            dep_module = Module.get(dependency)
            if dep_module is None:
                logger.error(f"Missing dependency {dependency}")
                return f"Missing dependency {dependency}"
            exec(dep_module.code, namespace)
            dependencies.append(namespace["function"])
        exec(self.code, namespace)
        retvals = namespace["function"](agent_id, casted_args, dependencies)
        retmsg = ""
        for i, (name, value) in enumerate(retvals.items()):
            retmsg += f"{name} = "
            if type(value) == int:
                retmsg += hex(value)
            elif type(value) == str:
                retmsg += value
            elif type(value) == bytes:
                retmsg += value.hex()
            else:
                retmsg += "Unrecognized type"
            if i != len(retvals) -1:
                retmsg += ", "
        return retmsg


    @classmethod
    def get(cls,name):
        session = get_session()
        stmt = (select(cls)
                    .where(cls.name == name)
                    .order_by(cls.id.asc())
                    .limit(1)
                )
        res_obj = session.execute(stmt).scalar_one_or_none()
        return res_obj

    @classmethod
    def get_help(cls):
        helpmsg = "Available modules: \n"
        modules = cls.all()
        for module in modules:
            helpmsg += module.get_module_help()
        return helpmsg