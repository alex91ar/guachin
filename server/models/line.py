from models.basemodel import Base, db
from sqlalchemy.sql import func


class Line(Base):
    __tablename__ = "lines"
    id = db.Column(db.Integer, primary_key=True)
    shell_id = db.Column(db.String(255), db.ForeignKey("shells.id"), nullable=False)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)
    incoming = db.Column(db.Boolean, nullable=False, default=False)

    def to_dict(self):
        return {
            "id": self.id,
            "shell_id": self.shell_id,
            "content": self.content,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "incoming": self.incoming,
        }
    
    @classmethod
    def by_shell_incoming_after(cls, shell_id: str, last_id: int = 0):
        db.session.remove()
        return (
            cls.query
            .filter(
                cls.shell_id == shell_id,
                cls.incoming == 1,
                cls.id > last_id,
            )
            .order_by(cls.id.asc())
            .all()
        )
    @classmethod
    def by_shell_outgoing_after(cls, shell_id: str, last_id: int = 0):
        db.session.remove()
        return (
            cls.query
            .filter(
                cls.shell_id == shell_id,
                cls.incoming == 0,
                cls.id > last_id,
            )
            .order_by(cls.id.asc())
            .all()
        )

    @classmethod
    def create_for_shell(cls, shell_id: str, content: str, incoming: bool):
        line = cls(shell_id=shell_id, content=content, incoming=incoming)
        db.session.add(line)
        db.session.commit()
        return line

    def __init__(self, shell_id, content, incoming=False):
        self.shell_id = shell_id
        self.content = content
        self.incoming = incoming