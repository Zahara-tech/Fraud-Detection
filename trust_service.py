"""
services/trust_service.py
Manages receiver trust scores.
Trust reflects how reliably safe a receiver has been historically.

Trust Score Logic:
  - Flagged/blacklisted receiver       → 0.0 (zero trust)
  - New receiver (no history)          → 0.2 (low trust)
  - Receiver with few txns (<5)        → 0.3–0.5
  - High new_sender_ratio              → penalize trust
  - Many transactions + known senders  → up to 0.95
"""

from sqlalchemy.orm import Session
from app.models.receiver_profile import ReceiverProfile
from app.models.user import User


def get_or_create_profile(db: Session, receiver_id: str) -> ReceiverProfile:
    """Fetch receiver profile, or create a blank one if first time."""
    profile = db.query(ReceiverProfile).filter(
        ReceiverProfile.receiver_id == receiver_id
    ).first()

    if not profile:
        profile = ReceiverProfile(receiver_id=receiver_id)
        db.add(profile)
        db.commit()
        db.refresh(profile)

    return profile


def compute_trust_score(profile: ReceiverProfile, receiver_user: User | None) -> float:
    """
    Compute trust score from 0.0 to 1.0.

    Factors:
      1. Is receiver blacklisted?     → instant 0.0
      2. Is receiver a known user?    → base bonus
      3. Transaction volume           → more = higher trust
      4. new_sender_ratio             → high ratio = suspicious
      5. Flagged profile              → 0.0
    """
    # Hard zero for flagged / blacklisted
    if profile.is_flagged:
        return 0.0
    if receiver_user and receiver_user.is_blacklisted:
        return 0.0

    score = 0.0

    # Factor 1: Is this a registered user?
    if receiver_user:
        score += 0.20   # Known account base

    # Factor 2: Transaction history volume
    txn_count = profile.total_received
    if txn_count == 0:
        pass                          # No history → no volume bonus
    elif txn_count < 3:
        score += 0.10
    elif txn_count < 10:
        score += 0.25
    elif txn_count < 30:
        score += 0.35
    else:
        score += 0.45                 # Very active receiver

    # Factor 3: Unique senders diversity (many senders = more trusted network)
    unique = profile.unique_senders
    if unique >= 10:
        score += 0.20
    elif unique >= 5:
        score += 0.10
    elif unique >= 2:
        score += 0.05

    # Factor 4: Penalize high new-sender ratio (many strangers = suspicious)
    new_ratio = profile.new_sender_ratio
    if new_ratio > 0.8:
        score -= 0.20
    elif new_ratio > 0.6:
        score -= 0.10
    elif new_ratio > 0.4:
        score -= 0.05

    # Clamp between 0.05 and 0.95
    return round(max(0.05, min(0.95, score)), 3)


def update_receiver_profile(
    db: Session,
    receiver_id: str,
    sender_id: str,
    amount: float
) -> ReceiverProfile:
    """
    Called AFTER a transaction completes successfully.
    Updates aggregated metrics for the receiver profile.
    """
    profile = get_or_create_profile(db, receiver_id)

    # Track if this sender is new to this receiver
    # Simple heuristic: check existing transactions in DB
    from app.models.transaction import Transaction
    past_sender_txns = db.query(Transaction).filter(
        Transaction.receiver_id == receiver_id,
        Transaction.sender_id == sender_id,
        Transaction.status == "Completed"
    ).count()

    is_new_sender = past_sender_txns == 0

    profile.total_received += 1
    profile.total_amount   += amount

    if is_new_sender:
        profile.unique_senders += 1

    # Recompute rolling average
    profile.avg_received_amount = profile.total_amount / profile.total_received

    # Recompute new_sender_ratio
    profile.new_sender_ratio = round(profile.unique_senders / profile.total_received, 3)

    # Recompute trust score
    receiver_user = db.query(User).filter(User.id == receiver_id).first()
    profile.trust_score = compute_trust_score(profile, receiver_user)

    db.commit()
    db.refresh(profile)
    return profile
