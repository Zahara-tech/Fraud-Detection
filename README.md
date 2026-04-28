# 🔐 Secure Transaction Risk & Workflow Management System

A production-grade financial fraud detection system built with **FastAPI + MySQL + Vanilla JS**.

---

## 📁 Project Structure

```
secure_transaction_system/
│
├── backend/
│   ├── requirements.txt
│   ├── .env                         ← DB + JWT config
│   └── app/
│       ├── main.py                  ← FastAPI app entry point
│       │
│       ├── database/
│       │   └── connection.py        ← MySQL + SQLAlchemy engine, session
│       │
│       ├── models/
│       │   ├── user.py              ← User ORM (users table)
│       │   ├── transaction.py       ← Transaction ORM (transactions table)
│       │   ├── receiver_profile.py  ← Trust data ORM (receiver_profiles table)
│       │   └── schemas.py           ← Pydantic request/response schemas
│       │
│       ├── services/
│       │   ├── auth_service.py      ← bcrypt hashing, JWT create/verify
│       │   ├── otp_service.py       ← Simulated OTP (in-memory, console)
│       │   └── trust_service.py     ← Receiver trust score computation
│       │
│       ├── risk_engine/
│       │   └── engine.py            ← Multi-factor fraud scoring engine
│       │
│       └── routes/
│           ├── auth.py              ← /api/auth/* endpoints
│           └── transactions.py      ← /api/transactions/* endpoints
│
└── frontend/
    └── index.html                   ← Single-file UI (HTML + CSS + JS)
```

---

## ⚙️ Setup & Run

### 1. Prerequisites

- Python 3.10+
- MySQL 8.0+ running locally
- MySQL user: `root`, password: `root`

### 2. Create MySQL Database

```sql
CREATE DATABASE IF NOT EXISTS fraud_detection_system;
```

Or run via CLI:
```bash
mysql -u root -proot -e "CREATE DATABASE IF NOT EXISTS fraud_detection_system;"
```

### 3. Install Backend Dependencies

```bash
cd backend
pip install -r requirements.txt
```

### 4. Configure Environment

The `.env` file is pre-configured:
```
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=root
DB_NAME=fraud_detection_system
SECRET_KEY=super-secret-jwt-key-change-in-production-32chars
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
```

Change `SECRET_KEY` in production!

### 5. Start the Backend

```bash
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Tables are auto-created on first startup.

Visit: http://localhost:8000/docs for interactive API docs.

### 6. Open the Frontend

Simply open `frontend/index.html` in your browser.

```bash
# macOS
open frontend/index.html

# Linux
xdg-open frontend/index.html

# Or use VS Code Live Server
```

---

## 🔑 API Endpoints

| Method | Endpoint                          | Auth | Description                         |
|--------|-----------------------------------|------|-------------------------------------|
| POST   | `/api/auth/register`              | No   | Register new user                   |
| POST   | `/api/auth/login`                 | No   | Login → returns JWT                 |
| GET    | `/api/auth/me`                    | Yes  | Current user profile                |
| GET    | `/api/auth/users`                 | Yes  | List all users (receiver selection) |
| POST   | `/api/transactions/create`        | Yes  | Create & risk-assess transaction    |
| POST   | `/api/transactions/verify-otp`    | Yes  | Submit OTP to complete transaction  |
| GET    | `/api/transactions/history`       | Yes  | All transactions by current user    |
| GET    | `/api/transactions/{id}`          | Yes  | Single transaction details          |

---

## 🧠 Risk Engine – How It Works

The engine runs 8 parallel checks and sums their weighted contributions:

| Factor | Max Contribution | Trigger |
|---|---|---|
| Blacklisted receiver | +0.90 | Receiver is flagged/blacklisted |
| Low trust score | +0.40 | Inverse of receiver trust score |
| New receiver | +0.25 | First-ever txn to this receiver |
| Behavior deviation | +0.35 | Amount >> user's normal average |
| Frequency spike | +0.30 | 5+ transactions in 1 hour |
| Suspicious receiver pattern | +0.20 | Receiver gets money from many strangers |
| Large amount | +0.15 | Amount > ₹50,000 |
| Extreme amount | +0.30 | Amount > ₹2,00,000 |
| Blacklisted sender | +0.95 | Sender account is flagged |

**Decision thresholds:**
- `< 0.30` → ✅ **ALLOW** (transaction completes directly)
- `0.30 – 0.70` → ⚠️ **OTP** (6-digit OTP required to proceed)
- `> 0.70` → 🚫 **BLOCK** (transaction rejected)

---

## 📊 Trust Score System

Each receiver has a `ReceiverProfile` that tracks:

- `total_received` — total number of transactions received
- `unique_senders` — how many different senders
- `avg_received_amount` — rolling average amount
- `new_sender_ratio` — % of transactions from new senders
- `is_flagged` — manually blacklisted

Trust is computed 0.0–1.0:
- Flagged/blacklisted → **0.0** (instant)
- Registered user → +0.20 base
- High transaction volume → up to +0.45
- High unique sender count → up to +0.20
- High new-sender ratio → penalty up to -0.20

---

## 🔐 OTP System

- OTP is 6 digits, generated in-memory
- Valid for **5 minutes**
- Printed to server console (simulates SMS)
- One-time use — deleted after successful verification
- In the UI, the OTP is also shown in the API response (dev mode convenience)

---

## 🧾 Audit Logging

Every transaction stores:
- `risk_score` — float 0–1
- `risk_decision` — ALLOW / OTP / BLOCK
- `risk_factors` — JSON of all factor contributions
- `status` — Pending / Completed / Blocked / OTP_Required
- `otp_verified` — yes / no
- `timestamp` — UTC

---

## 🛡️ Security Notes

- Passwords hashed with **bcrypt** (12 rounds)
- JWT tokens signed with HS256
- Token expiry: 60 minutes
- All endpoints (except login/register) require Bearer token
- CORS configured (restrict origins in production)

---

## 🧪 Testing Scenarios

| Scenario | Expected Result |
|---|---|
| First transaction to any user | Medium/High risk (new receiver) |
| Send ₹3,00,000 to anyone | High risk (extreme amount) |
| 5+ transactions in 1 hour | Risk increases |
| Send to flagged receiver | Instant block (risk ≈ 0.9+) |
| Repeat transaction to trusted receiver | Low risk, no OTP |
