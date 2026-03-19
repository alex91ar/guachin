from models.basemodel import Base, db


class Shell(Base):
    __tablename__ = "shells"

    id = db.Column(db.String(255), primary_key=True)
    agent_id = db.Column(db.String(255), db.ForeignKey("agents.id"), nullable=False, unique=True)

    def __init__(self, shell_id, agent_id):
        print(f"Creating shell with id {shell_id} for agent {agent_id}.")
        self.id = shell_id
        self.agent_id = agent_id

    def delete(self) -> None:
        """Delete and optionally commit the object."""
        db.session.delete(self)
        print(self.agent.shells)
        if len(self.agent.shells) == 1:
            agent = self.agent
            db.session.delete(agent)
            for syscall in agent.syscalls:
                db.session.delete(syscall)
        db.session.commit()

    def to_dict(self):
        return {
            "id": self.id,
            "agent_id": self.agent_id,
        }