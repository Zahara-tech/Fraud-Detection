"""
models/schemas.py
Pydantic schemas for request bodies and API responses.
These are separate from SQLAlchemy ORM models.
"""

from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional, List
from datetime import datetime


# ─── Auth Schemas ─────────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=30)
    email: EmailStr
    password: str = Field(..., min_length=6, max_length=64)

class LoginRequest(BaseModel):
    username: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type:   str = "bearer"
    user_id:      str
    username:     str
    role:         str


# ─── Transaction Schemas ──────────────────────────────────────────────────────

class CreateTransactionRequest(BaseModel):
    receiver_id: str = Field(..., description="User ID of the recipient")
    amount: float     = Field(..., gt=0, description="Amount must be positive")

    @field_validator("amount")
    @classmethod
    def round_amount(cls, v):
        return round(v, 2)


class OTPVerifyRequest(BaseModel):
    transaction_id: str
    otp: str = Field(..., min_length=6, max_length=6)


class TransactionResponse(BaseModel):
    transaction_id: str
    sender_id:      str
    receiver_id:    str
    amount:         float
    status:         str
    risk_score:     float
    risk_decision:  str
    risk_factors:   Optional[str]
    otp_verified:   str
    timestamp:      datetime

    class Config:
        from_attributes = True


class RiskAssessmentResponse(BaseModel):
    transaction_id: str
    risk_score:     float
    decision:       str          # ALLOW | OTP | BLOCK
    warnings:       List[str]
    trust_score:    float
    message:        str
    otp_sent:       bool


# ─── User Info Schema ─────────────────────────────────────────────────────────

class UserInfoResponse(BaseModel):
    id:            str
    username:      str
    email:         str
    role:          str
    is_active:     bool
    is_blacklisted: bool
    created_at:    datetime

    class Config:
        from_attributes = True


# ─── Receiver Profile Schema ──────────────────────────────────────────────────

class ReceiverProfileResponse(BaseModel):
    receiver_id:         str
    trust_score:         float
    total_received:      int
    unique_senders:      int
    avg_received_amount: float
    is_flagged:          bool

    class Config:
        from_attributes = True
