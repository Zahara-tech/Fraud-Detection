"""
models/user.py
SQLAlchemy ORM model for the 'users' table.
Stores credentials, role, and account status.
"""

from sqlalchemy import Column, String, Boolean, DateTime, Enum
from sqlalchemy.sql import func
import uuid
from app.database.connection import Base


class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    username = Column(String(80), unique=True, nullable=False, index=True)
    email = Column(String(120), unique=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    role = Column(Enum("user", "admin"), default="user", nullable=False)
    is_active = Column(Boolean, default=True)
    is_blacklisted = Column(Boolean, default=False)   # Flagged fraudulent account
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<User {self.username} | role={self.role}>"
