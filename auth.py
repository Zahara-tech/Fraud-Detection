"""
routes/auth.py
Handles user registration and login.
Returns JWT on successful login.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.models.user import User
from app.models.schemas import RegisterRequest, LoginRequest, TokenResponse, UserInfoResponse
from app.services.auth_service import hash_password, verify_password, create_access_token, get_current_user

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


@router.post("/register", status_code=201, summary="Register a new user")
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    """
    Create a new user account.
    Validates username/email uniqueness, hashes password before storing.
    """
    # Check uniqueness
    if db.query(User).filter(User.username == payload.username).first():
        raise HTTPException(status_code=400, detail="Username already taken.")
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(status_code=400, detail="Email already registered.")

    user = User(
        username=payload.username,
        email=payload.email,
        hashed_password=hash_password(payload.password),
        role="user"
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    return {
        "message": "Account created successfully.",
        "user_id": user.id,
        "username": user.username
    }


@router.post("/login", response_model=TokenResponse, summary="Login and get JWT")
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    """
    Authenticate user credentials.
    Returns a JWT access token valid for 60 minutes.
    """
    user = db.query(User).filter(User.username == payload.username).first()

    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password."
        )

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is deactivated.")

    token = create_access_token({"sub": user.id, "role": user.role})

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user_id=user.id,
        username=user.username,
        role=user.role
    )


@router.get("/me", response_model=UserInfoResponse, summary="Get current user info")
def me(current_user: User = Depends(get_current_user)):
    """Returns the profile of the currently authenticated user."""
    return current_user


@router.get("/users", summary="List all users (for receiver selection in UI)")
def list_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Returns all users except the current one.
    Used in the frontend to select a transaction receiver.
    """
    users = db.query(User).filter(
        User.id != current_user.id,
        User.is_active == True
    ).all()

    return [
        {"id": u.id, "username": u.username, "email": u.email}
        for u in users
    ]
