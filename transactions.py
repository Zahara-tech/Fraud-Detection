"""
routes/transactions.py
Full transaction lifecycle:
  1. POST /create         → Risk check → ALLOW/OTP/BLOCK
  2. POST /verify-otp     → Validate OTP → Complete transaction
  3. GET  /history        → Sender's transaction history
  4. GET  /{txn_id}       → Single transaction detail
"""

import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.models.user import User
from app.models.transaction import Transaction
from app.models.schemas import (
    CreateTransactionRequest,
    OTPVerifyRequest,
    TransactionResponse,
    RiskAssessmentResponse
)
from app.services.auth_service import get_current_user
from app.services.otp_service import generate_otp, verify_otp, has_pending_otp
from app.services.trust_service import update_receiver_profile
from app.risk_engine.engine import assess_risk

router = APIRouter(prefix="/api/transactions", tags=["Transactions"])


# ─── Step 1: Create Transaction (triggers risk engine) ───────────────────────

@router.post("/create", response_model=RiskAssessmentResponse, summary="Create and risk-assess a transaction")
def create_transaction(
    payload: CreateTransactionRequest,
    db: Session    = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Main transaction entry point.

    Flow:
      1. Validate receiver exists
      2. Run multi-factor risk engine
      3. BLOCK → reject immediately
         ALLOW → complete immediately (no OTP needed for low-risk)
         OTP   → store as OTP_Required, generate & send OTP
    """
    # ── Validate receiver ─────────────────────────────────────────────────────
    if payload.receiver_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot send money to yourself.")

    receiver = db.query(User).filter(User.id == payload.receiver_id).first()
    if not receiver:
        raise HTTPException(status_code=404, detail="Receiver not found.")

    # ── Run Risk Engine ───────────────────────────────────────────────────────
    risk_result = assess_risk(
        db          = db,
        sender      = current_user,
        receiver_id = payload.receiver_id,
        amount      = payload.amount
    )

    risk_score = risk_result["risk_score"]
    decision   = risk_result["decision"]
    warnings   = risk_result["warnings"]
    factors    = risk_result["factors"]

    # ── Create transaction record (initial state) ─────────────────────────────
    txn = Transaction(
        sender_id     = current_user.id,
        receiver_id   = payload.receiver_id,
        amount        = payload.amount,
        risk_score    = risk_score,
        risk_decision = decision,
        risk_factors  = json.dumps(factors),
        status        = "Pending"
    )

    # ── Apply Decision ────────────────────────────────────────────────────────

    if decision == "BLOCK":
        txn.status = "Blocked"
        db.add(txn)
        db.commit()
        db.refresh(txn)

        return RiskAssessmentResponse(
            transaction_id = txn.transaction_id,
            risk_score     = risk_score,
            decision       = "BLOCK",
            warnings       = warnings,
            trust_score    = risk_result["trust_score"],
            message        = "Transaction BLOCKED due to high fraud risk.",
            otp_sent       = False
        )

    elif decision == "ALLOW":
        # Low risk → complete directly, no OTP
        txn.status       = "Completed"
        txn.otp_verified = "no"
        db.add(txn)
        db.commit()
        db.refresh(txn)

        # Update receiver trust profile
        update_receiver_profile(db, payload.receiver_id, current_user.id, payload.amount)

        return RiskAssessmentResponse(
            transaction_id = txn.transaction_id,
            risk_score     = risk_score,
            decision       = "ALLOW",
            warnings       = warnings,
            trust_score    = risk_result["trust_score"],
            message        = "Transaction completed successfully.",
            otp_sent       = False
        )

    else:  # OTP required
        txn.status = "OTP_Required"
        db.add(txn)
        db.commit()
        db.refresh(txn)

        # Generate and "send" OTP (printed to console)
        otp = generate_otp(txn.transaction_id)

        return RiskAssessmentResponse(
            transaction_id = txn.transaction_id,
            risk_score     = risk_score,
            decision       = "OTP",
            warnings       = warnings,
            trust_score    = risk_result["trust_score"],
            message        = f"OTP required. Check console for your OTP. (Dev mode OTP: {otp})",
            otp_sent       = True
        )


# ─── Step 2: Verify OTP and Complete Transaction ──────────────────────────────

@router.post("/verify-otp", response_model=TransactionResponse, summary="Verify OTP to complete transaction")
def verify_otp_endpoint(
    payload: OTPVerifyRequest,
    db: Session    = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Validate OTP for a pending transaction.
    On success → marks Completed, updates receiver profile.
    On failure → returns 400 (OTP remains valid until expiry).
    """
    txn = db.query(Transaction).filter(
        Transaction.transaction_id == payload.transaction_id,
        Transaction.sender_id      == current_user.id
    ).first()

    if not txn:
        raise HTTPException(status_code=404, detail="Transaction not found.")

    if txn.status != "OTP_Required":
        raise HTTPException(
            status_code=400,
            detail=f"Transaction is in state '{txn.status}', not awaiting OTP."
        )

    if not has_pending_otp(payload.transaction_id):
        raise HTTPException(status_code=400, detail="OTP has expired. Please create a new transaction.")

    if not verify_otp(payload.transaction_id, payload.otp):
        raise HTTPException(status_code=400, detail="Incorrect OTP. Please try again.")

    # OTP verified → complete
    txn.status       = "Completed"
    txn.otp_verified = "yes"
    db.commit()
    db.refresh(txn)

    # Update receiver trust profile
    update_receiver_profile(db, txn.receiver_id, current_user.id, txn.amount)

    return txn


# ─── Transaction History ──────────────────────────────────────────────────────

@router.get("/history", summary="Get all transactions by current user")
def transaction_history(
    db: Session        = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Returns all transactions sent by the authenticated user, newest first."""
    txns = db.query(Transaction).filter(
        Transaction.sender_id == current_user.id
    ).order_by(Transaction.timestamp.desc()).all()

    results = []
    for t in txns:
        receiver = db.query(User).filter(User.id == t.receiver_id).first()
        results.append({
            "transaction_id": t.transaction_id,
            "receiver_id":    t.receiver_id,
            "receiver_name":  receiver.username if receiver else "Unknown",
            "amount":         t.amount,
            "status":         t.status,
            "risk_score":     t.risk_score,
            "risk_decision":  t.risk_decision,
            "otp_verified":   t.otp_verified,
            "timestamp":      t.timestamp.isoformat() if t.timestamp else None,
        })

    return results


@router.get("/{transaction_id}", response_model=TransactionResponse, summary="Get a single transaction")
def get_transaction(
    transaction_id: str,
    db: Session        = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Fetch a specific transaction (must be sender)."""
    txn = db.query(Transaction).filter(
        Transaction.transaction_id == transaction_id,
        Transaction.sender_id      == current_user.id
    ).first()

    if not txn:
        raise HTTPException(status_code=404, detail="Transaction not found.")

    return txn
