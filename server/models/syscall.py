from models.basemodel import Base, db
from sqlalchemy.exc import OperationalError


class Syscall(Base):
    __tablename__ = "syscalls"
    __table_args__ = (
        db.UniqueConstraint("agent_id", "name", name="uq_syscalls_agent_name"),
    )
    id = db.Column(db.Integer, primary_key=True)
    agent_id = db.Column(db.String(255), db.ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True)
    name = db.Column(db.String(255))
    syscall = db.Column(db.BigInteger)
    def __init__(self, agent_id, name, syscall):
        self.agent_id = agent_id
        self.name = name
        self.syscall = syscall

    def to_dict(self):
        return {
            "id": self.id,
            "agent_id": self.agent_id,
            "name": self.name,
            "syscall":self.syscall
        }
    

    @classmethod
    def save_syscalls_bytes(cls, agent_id, data: bytes, db_session):
        if not data:
            raise ValueError("Input string is empty")

        value = data.decode()

        try:
            objs = []

            for item in value.split(","):
                item = item.strip()
                if not item:
                    continue

                if ":" not in item:
                    raise ValueError(f"Invalid entry: {item}")

                name, syscall_str = item.split(":", 1)
                name = name.strip()
                syscall_str = syscall_str.strip()

                if not name:
                    raise ValueError(f"Missing API name in entry: {item}")

                try:
                    syscall_number = int(syscall_str)
                except ValueError:
                    raise ValueError(f"Invalid syscall number in entry: {item}")

                objs.append(Syscall(agent_id, name, syscall_number))

            db_session.add_all(objs)
            db_session.commit()

        except Exception:
            db_session.rollback()
            raise
       

    @classmethod
    def sys(cls, agent_id, name):
        row = cls.query.filter(
            cls.agent_id == agent_id,
            cls.name == name,
        ).first()

        if row is None:
            raise LookupError(f"Syscall not found for agent_id={agent_id}, name={name}")

        return row.syscall