# models/passkey.py
from __future__ import annotations
import base64
from models.basemodel import Base, db

class PassKey(Base):
    __tablename__ = "passkeys"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(255), db.ForeignKey("users.id"), nullable=False, index=True)

    credential_id = db.Column(db.String(255), unique=True, nullable=False)
    public_key = db.Column(db.LargeBinary, nullable=False)
    sign_count = db.Column(db.Integer, nullable=False, default=0)
    credential_data = db.Column(db.LargeBinary, nullable=False)  # ✅ add this

    @staticmethod
    def by_credential_id(user_id: str, credential_id: str) -> "PassKey|None":
        return PassKey.query.filter_by(user_id=user_id, credential_id=credential_id).first()


    @classmethod
    def all_by_user(self, user) -> dict:
        resp = super().all()
        for i in range(len(resp) - 1, -1, -1):
            if user is not None and resp[i].user_id != user:
                resp[i].delete()
        return resp

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "credential_id": self.credential_id,
            # bytes -> base64 for JSON
            "public_key_b64": base64.b64encode(self.public_key).decode("ascii"),
            "sign_count": self.sign_count,
        }
