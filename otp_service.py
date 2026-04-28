"""
services/otp_service.py
Simulated OTP system (no real SMS).
OTPs are stored in-memory (keyed by transaction_id).
In production, use Redis with TTL instead.
"""

import random
import time

# In-memory OTP store: { transaction_id: { otp, expires_at } }
_otp_store: dict = {}

OTP_TTL_SECONDS = 300  # OTP valid for 5 minutes


def generate_otp(transaction_id: str) -> str:
    """
    Generate a 6-digit OTP for a given transaction.
    Prints to console (simulating SMS delivery).
    """
    otp = str(random.randint(100000, 999999))
    _otp_store[transaction_id] = {
        "otp": otp,
        "expires_at": time.time() + OTP_TTL_SECONDS
    }
    # Simulated delivery
    print(f"\n{'='*50}")
    print(f"  [OTP SERVICE] Transaction: {transaction_id[:12]}...")
    print(f"  Your OTP is: {otp}  (valid 5 min)")
    print(f"{'='*50}\n")
    return otp


def verify_otp(transaction_id: str, otp_input: str) -> bool:
    """
    Verify OTP for a transaction.
    Returns True if valid and not expired.
    Cleans up after successful verification.
    """
    record = _otp_store.get(transaction_id)

    if not record:
        return False  # No OTP generated for this transaction

    if time.time() > record["expires_at"]:
        del _otp_store[transaction_id]
        return False  # Expired

    if record["otp"] != otp_input.strip():
        return False  # Wrong OTP

    del _otp_store[transaction_id]  # One-time use
    return True


def has_pending_otp(transaction_id: str) -> bool:
    """Check if an OTP is currently pending for this transaction."""
    record = _otp_store.get(transaction_id)
    if not record:
        return False
    if time.time() > record["expires_at"]:
        del _otp_store[transaction_id]
        return False
    return True
