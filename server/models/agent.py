from datetime import datetime
from sqlalchemy.orm import relationship

from models.basemodel import Base, db


class Agent(Base):
    __tablename__ = "agents"

    id = db.Column(db.String(255), primary_key=True)
    ip = db.Column(db.String(255), nullable=True)
    os = db.Column(db.BigInteger, nullable=True)
    online = db.Column(db.Boolean, nullable=False, default=False)
    last_seen = db.Column(db.DateTime(timezone=True), nullable=True)
    user_id = db.Column(db.String(255), db.ForeignKey("users.id"), nullable=True)
    scratchpad = db.Column(db.BigInteger, nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "ip": self.ip,
            "os": self.os, 
            "last_seen": self.last_seen.isoformat() if self.last_seen else None,
            "user_id": self.user_id,
        }

    def __init__(self, id, user_id):
        self.id = id
        self.last_seen = datetime.now()
        self.user_id = user_id

    @classmethod
    def by_user_name(cls, user_name: str):
        return cls.query.filter_by(user_id=user_name)