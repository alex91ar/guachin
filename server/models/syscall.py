from models.basemodel import Base, db


class Syscall(Base):
    __tablename__ = "syscalls"

    id = db.Column(db.Integer, primary_key=True)
    agent_id = db.Column(db.String(255), db.ForeignKey("agents.id"), nullable=False)
    name = db.Column(db.String(255))
    syscall = db.Column(db.Integer)
    def __init__(self, agent_id, name, syscall):
        print(f"Creating syscall agent_id {agent_id} name {name} syscall {syscall}.")
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
    def sys(cls, agent_id, name):
        return cls.query.filter(
                cls.agent_id == agent_id,
                cls.name == name,
            ).one().syscall