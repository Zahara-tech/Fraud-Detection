"""
database/connection.py
Handles MySQL connection using SQLAlchemy.
Creates engine, session factory, and a Base for all ORM models.
"""

from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker
import os
from dotenv import load_dotenv

load_dotenv()

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "3306")
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "root")
DB_NAME = os.getenv("DB_NAME", "fraud_detection_system")

DATABASE_URL = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,          # Verify connection is alive before use
    pool_recycle=300,            # Recycle connections every 5 minutes
    echo=False                   # Set True to log SQL queries for debugging
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """
    FastAPI dependency that provides a DB session per request.
    Always closes the session after the request completes.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """
    Create all tables in the database if they don't exist.
    Called once on application startup.
    """
    from app.models import user, transaction, receiver_profile  # noqa: F401
    Base.metadata.create_all(bind=engine)
    print("[DB] All tables created / verified.")
