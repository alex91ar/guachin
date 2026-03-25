from models.basemodel import Base, db
from sqlalchemy.sql import func
import struct

class Response(Base):
    __tablename__ = "responses"
    id = db.Column(db.Integer, primary_key=True)
    agent_id = db.Column(db.String(255), db.ForeignKey("agents.id"), nullable=False)
    content = db.Column(db.LargeBinary, nullable=False)
    timestamp = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)
    content = db.Column(db.LargeBinary, nullable=True)
    request = db.Column(db.Integer,db.ForeignKey("requests.id", ondelete="CASCADE"),nullable=True,index=True)
    received = db.Column(db.Boolean, nullable=False, default=False)

    def to_dict(self):
        return {
            "id": self.id,
            "agent_id": self.agent_id,
            "content": self.content,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
        }

    def __init__(self, agent_id, content, request_id):
        self.agent_id = agent_id
        self.content = content
        self.request = request_id
    
    @classmethod
    def by_agent(cls, agent_id):
        return cls.query.filter_by(agent_id = agent_id, received = False).first()