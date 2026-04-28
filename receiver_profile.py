"""
models/receiver_profile.py
Stores aggregated trust data for each receiver.
Updated every time a transaction targets this receiver.
Used by the risk engine to compute trust scores.
"""

from sqlalchemy import Column, String, Float, Integer, DateTime, Boolean
from sqlalchemy.sql import func
from app.database.connection import Base


class ReceiverProfile(Base):
    __tablename__ = "receiver_profiles"

    receiver_id         = Column(String(36), primary_key=True)

    # Trust metrics
    trust_score         = Column(Float, default=0.5)    # 0.0 – 1.0
    total_received      = Column(Integer, default=0)    # How many txns received
    unique_senders      = Column(Integer, default=0)    # Distinct senders
    total_amount        = Column(Float, default=0.0)    # Cumulative amount received
    is_flagged          = Column(Boolean, default=False) # Manually flagged

    # Behavior signals
    avg_received_amount = Column(Float, default=0.0)    # Rolling average amount
    new_sender_ratio    = Column(Float, default=1.0)    # % of txns from new senders

    first_seen          = Column(DateTime(timezone=True), server_default=func.now())
    last_seen           = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())

    def __repr__(self):
        return f"<ReceiverProfile {self.receiver_id[:8]}… | trust={self.trust_score:.2f}>"
