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
        i = 0
        import struct

        if not data:
            raise ValueError("Input string is empty")

        try:
            objs = []
            seen = set()

            # 🔑 Fetch existing syscall names from DB
            existing = set(
                name for (name,) in db_session.query(Syscall.name)
                .filter(Syscall.agent_id == agent_id)
                .all()
            )

            while i < len(data):
                name_len = data[i]
                name = data[i+1 : i+1+name_len].decode('ascii')
                value = struct.unpack('<Q', data[i+1+name_len : i+1+name_len+8])[0]
                i += (1 + name_len + 8)


                if name in seen or name in existing:
                    continue

                seen.add(name)
                objs.append(Syscall(agent_id, name, value))

            if objs:
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