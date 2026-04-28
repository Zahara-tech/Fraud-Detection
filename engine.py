"""
risk_engine/engine.py
─────────────────────────────────────────────────────────
CORE FRAUD DETECTION ENGINE
─────────────────────────────────────────────────────────

Multi-factor risk scoring system. Each factor contributes
a weighted score. Final score 0.0–1.0 determines the action.

Factors:
  F1. Blacklisted receiver               → +0.90 (near-instant block)
  F2. Receiver trust score               → inverse mapping
  F3. New receiver (no history)          → +0.25
  F4. Amount deviation from user norm    → scaled penalty
  F5. Transaction frequency spike        → +0.15 per spike
  F6. Suspicious receiver pattern        → +0.20 (many unknown senders)
  F7. High single-shot amount            → +0.10–0.30
  F8. Blacklisted sender                 → +0.95

Decision thresholds:
  risk < 0.30  → ALLOW  (complete immediately)
  0.30–0.70    → OTP    (require OTP verification)
  risk > 0.70  → BLOCK  (reject transaction)
"""

import json
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.transaction import Transaction
from app.models.receiver_profile import ReceiverProfile
from app.services.trust_service import get_or_create_profile, compute_trust_score


# ─── Thresholds ──────────────────────────────────────────────────────────────

RISK_ALLOW  = 0.30
RISK_BLOCK  = 0.70

# Amount considered "large" (absolute, in currency units)
LARGE_AMOUNT_THRESHOLD   = 50_000
EXTREME_AMOUNT_THRESHOLD = 200_000

# How many transactions per hour triggers frequency alert
FREQUENCY_SPIKE_PER_HOUR = 5

# ─── Main Risk Assessment ─────────────────────────────────────────────────────

def assess_risk(
    db: Session,
    sender: User,
    receiver_id: str,
    amount: float
) -> dict:
    """
    Run full risk assessment for a proposed transaction.

    Returns:
        {
            "risk_score": float,
            "decision":   "ALLOW" | "OTP" | "BLOCK",
            "factors":    { factor_name: contribution },
            "warnings":   [str]
        }
    """
    factors  = {}
    warnings = []

    # ── Fetch supporting data ────────────────────────────────────────────────

    receiver_user    = db.query(User).filter(User.id == receiver_id).first()
    receiver_profile = get_or_create_profile(db, receiver_id)

    # Sender's past completed transactions
    sender_history = db.query(Transaction).filter(
        Transaction.sender_id == sender.id,
        Transaction.status == "Completed"
    ).all()

    # ── F1: Blacklisted / flagged receiver ───────────────────────────────────
    if receiver_profile.is_flagged or (receiver_user and receiver_user.is_blacklisted):
        factors["blacklisted_receiver"] = 0.90
        warnings.append("Receiver account is blacklisted or flagged for fraud.")
    else:
        factors["blacklisted_receiver"] = 0.0

    # ── F2: Receiver trust score (inverse) ───────────────────────────────────
    trust = compute_trust_score(receiver_profile, receiver_user)
    # Low trust → high risk. Map trust 0→0.40 risk, trust 1→0.0 risk
    trust_risk = round((1 - trust) * 0.40, 3)
    factors["low_trust_receiver"] = trust_risk
    if trust < 0.30:
        warnings.append(f"Receiver has a low trust score ({trust:.2f}).")

    # ── F3: New receiver (no prior txns with this sender) ────────────────────
    prior_with_receiver = [t for t in sender_history if t.receiver_id == receiver_id]
    if len(prior_with_receiver) == 0:
        factors["new_receiver"] = 0.25
        warnings.append("This is your first transaction to this receiver.")
    else:
        factors["new_receiver"] = 0.0

    # ── F4: Deviation from sender's normal behavior ───────────────────────────
    if sender_history:
        amounts = [t.amount for t in sender_history]
        avg_amount = sum(amounts) / len(amounts)
        if avg_amount > 0:
            deviation_ratio = amount / avg_amount
            if deviation_ratio > 10:
                dev_risk = 0.35
                warnings.append(
                    f"Amount is {deviation_ratio:.1f}x your average (₹{avg_amount:,.0f})."
                )
            elif deviation_ratio > 5:
                dev_risk = 0.20
                warnings.append(
                    f"Amount is {deviation_ratio:.1f}x your average (₹{avg_amount:,.0f})."
                )
            elif deviation_ratio > 3:
                dev_risk = 0.10
            else:
                dev_risk = 0.0
        else:
            dev_risk = 0.0
    else:
        # No history = first transaction, mild uncertainty
        dev_risk = 0.08
    factors["behavior_deviation"] = round(dev_risk, 3)

    # ── F5: Transaction frequency spike ──────────────────────────────────────
    one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
    recent_txns = db.query(Transaction).filter(
        Transaction.sender_id == sender.id,
        Transaction.timestamp >= one_hour_ago
    ).count()

    if recent_txns >= FREQUENCY_SPIKE_PER_HOUR:
        freq_risk = min(0.30, 0.06 * recent_txns)
        factors["frequency_spike"] = round(freq_risk, 3)
        warnings.append(f"High frequency: {recent_txns} transactions in the last hour.")
    else:
        factors["frequency_spike"] = 0.0

    # ── F6: Suspicious receiver pattern (many unknown senders) ───────────────
    if receiver_profile.new_sender_ratio > 0.75 and receiver_profile.total_received >= 5:
        factors["suspicious_receiver_pattern"] = 0.20
        warnings.append("Receiver receives money from many unknown senders (potential mule account).")
    else:
        factors["suspicious_receiver_pattern"] = 0.0

    # ── F7: Large or extreme amount ───────────────────────────────────────────
    if amount >= EXTREME_AMOUNT_THRESHOLD:
        factors["extreme_amount"] = 0.30
        warnings.append(f"Transaction amount ₹{amount:,.0f} is extremely large.")
    elif amount >= LARGE_AMOUNT_THRESHOLD:
        factors["large_amount"] = 0.15
        warnings.append(f"Transaction amount ₹{amount:,.0f} is above normal limits.")
    else:
        factors["large_amount"] = 0.0
        factors["extreme_amount"] = 0.0

    # ── F8: Sender is blacklisted ─────────────────────────────────────────────
    if sender.is_blacklisted:
        factors["blacklisted_sender"] = 0.95
        warnings.append("Your account has been flagged. Transaction blocked.")

    # ── Aggregate Score ───────────────────────────────────────────────────────
    raw_score = sum(factors.values())

    # Cap at 1.0; apply a soft sigmoid-like curve for mid-range values
    risk_score = round(min(1.0, raw_score), 4)

    # ── Decision ──────────────────────────────────────────────────────────────
    if risk_score < RISK_ALLOW:
        decision = "ALLOW"
    elif risk_score <= RISK_BLOCK:
        decision = "OTP"
    else:
        decision = "BLOCK"

    return {
        "risk_score": risk_score,
        "decision":   decision,
        "factors":    factors,
        "warnings":   warnings,
        "trust_score": trust
    }
