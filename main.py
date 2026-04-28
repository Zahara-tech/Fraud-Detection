"""
app/main.py
─────────────────────────────────────────────────────────
Entry point for the Secure Transaction Risk & Workflow
Management System backend API.

Starts FastAPI, mounts all routers, initializes the DB.
Run with: uvicorn app.main:app --reload
─────────────────────────────────────────────────────────
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database.connection import init_db
from app.routes.auth import router as auth_router
from app.routes.transactions import router as transaction_router

# ─── App Initialization ───────────────────────────────────────────────────────

app = FastAPI(
    title        = "Secure Transaction Risk & Workflow Management System",
    description  = "Financial fraud detection API with JWT auth, risk engine, and OTP verification.",
    version      = "1.0.0",
    docs_url     = "/docs",
    redoc_url    = "/redoc"
)

# ─── CORS (allow frontend dev server) ────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins     = ["*"],   # Restrict to specific origin in production
    allow_credentials = True,
    allow_methods     = ["*"],
    allow_headers     = ["*"],
)

# ─── Routers ──────────────────────────────────────────────────────────────────

app.include_router(auth_router)
app.include_router(transaction_router)

# ─── Startup Event ────────────────────────────────────────────────────────────

@app.on_event("startup")
def startup():
    """Initialize database tables on first run."""
    init_db()
    print("[APP] Backend started. Visit http://localhost:8000/docs")

# ─── Health Check ─────────────────────────────────────────────────────────────

@app.get("/", tags=["Health"])
def root():
    return {"status": "ok", "message": "Secure Transaction API is running."}

@app.get("/health", tags=["Health"])
def health():
    return {"status": "healthy"}
