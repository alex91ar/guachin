import time
from models.basemodel import Base, db
from sqlalchemy.sql import func
from models.db import get_session
from sqlalchemy import select
from sqlalchemy.dialects.mysql import LONGBLOB


class Request(Base):
    __tablename__ = "requests"

    id = db.Column(db.Integer, primary_key=True)
    agent_id = db.Column(db.String(255), db.ForeignKey("agents.id", ondelete="CASCADE"), nullable=False)
    content = db.Column(db.LargeBinary, nullable=True)
    timestamp = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)
    response = db.Column(LONGBLOB, nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "agent_id": self.agent_id,
            "content": self.content,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "response": self.response,
            "sent": self.sent,
        }

    def __init__(self, agent_id, content, timeout=10, interval=0.2):
        self.agent_id = agent_id
        self.content = content

        session = get_session()

        session.add(self)
        session.commit()

    @classmethod
    def by_id(cls, id: str):
        return cls.query.get(id)


    @classmethod
    def by_agent(cls, agent_id, last_request_id):
        session = get_session()

        try:
            stmt = (
                select(cls)
                .where(cls.agent_id == agent_id, cls.id > last_request_id)
                .order_by(cls.id.desc())
                .limit(1)
            )
            return session.execute(stmt).scalar_one_or_none()
        finally:
            session.close()
    
    @classmethod
    def by_id_session(cls, id, session=None):
        owns_session = session is None
        session = session or get_session()
        try:
            return session.get(cls, id)
        finally:
            if owns_session:
                session.close()