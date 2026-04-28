"""
models/transaction.py
SQLAlchemy ORM model for the 'transactions' table.
Stores every transaction with its risk score, status, and audit fields.
"""

from sqlalchemy import Column, String, Float, DateTime, Enum, Text
from sqlalchemy.sql import func
import uuid
from app.database.connection import Base


class Transaction(Base):
    __tablename__ = "transactions"

    transaction_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    sender_id     = Column(String(36), nullable=False, index=True)
    receiver_id   = Column(String(36), nullable=False, index=True)
    amount        = Column(Float, nullable=False)

    # Risk fields
    risk_score    = Column(Float, default=0.0)          # 0.0 – 1.0
    risk_decision = Column(String(20), default="ALLOW") # ALLOW | OTP | BLOCK

    # Status of the transaction lifecycle
    status = Column(
        Enum("Pending", "Completed", "Blocked", "OTP_Required"),
        default="Pending",
        nullable=False
    )

    # Audit / logging fields
    risk_factors  = Column(Text, nullable=True)   # JSON string of contributing factors
    otp_verified  = Column(String(5), default="no")  # yes / no
    timestamp     = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<Txn {self.transaction_id[:8]}… | {self.status} | risk={self.risk_score:.2f}>"
