from models.basemodel import Base, db
from sqlalchemy.sql import func
import struct
from sqlalchemy import select
import time
from models.db import get_session


class Response(Base):
    __tablename__ = "responses"
    id = db.Column(db.Integer, primary_key=True)
    agent_id = db.Column(db.String(255), db.ForeignKey("agents.id", ondelete="CASCADE"), nullable=False)
    content = db.Column(db.LargeBinary, nullable=False)
    timestamp = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)
    content = db.Column(db.LargeBinary, nullable=True)
    request = db.Column(db.Integer,db.ForeignKey("requests.id", ondelete="CASCADE"),nullable=True,index=True)

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
        session = get_session()

        session.add(self)
        session.commit()
    
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
    def by_request_id(cls, request_id):
        session = get_session()

        try:
            while True:
                stmt = (
                    select(cls)
                    .where(cls.request == request_id)
                    .order_by(cls.id.asc())
                    .limit(1)
                )
                res_obj = session.execute(stmt).scalar_one_or_none()
                if res_obj is not None:
                    return res_obj
        finally:
            session.close()