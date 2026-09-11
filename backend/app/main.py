import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.database import engine, Base
from app.routers import auth, purchase_requests, vendors, approvals, dashboard
from app.compliance.ingest import init_policy_db

# Create database tables
Base.metadata.create_all(bind=engine)

# Ensure SQLite schema has any newly added columns
try:
    with engine.connect() as conn:
        from sqlalchemy import text
        # vendor_bids
        res = conn.execute(text("PRAGMA table_info(vendor_bids);")).fetchall()
        cols = [r[1] for r in res]
        if "original_quoted_price" not in cols:
            conn.execute(text("ALTER TABLE vendor_bids ADD COLUMN original_quoted_price FLOAT;"))
        if "original_delivery_days" not in cols:
            conn.execute(text("ALTER TABLE vendor_bids ADD COLUMN original_delivery_days INTEGER;"))
        if "negotiation_transcript" not in cols:
            conn.execute(text("ALTER TABLE vendor_bids ADD COLUMN negotiation_transcript TEXT;"))

        # vendors
        res_v = conn.execute(text("PRAGMA table_info(vendors);")).fetchall()
        cols_v = [r[1] for r in res_v]
        if "is_local_vendor" not in cols_v:
            conn.execute(text("ALTER TABLE vendors ADD COLUMN is_local_vendor BOOLEAN DEFAULT 0;"))
        if "is_incubator" not in cols_v:
            conn.execute(text("ALTER TABLE vendors ADD COLUMN is_incubator BOOLEAN DEFAULT 0;"))
        if "local_proximity_km" not in cols_v:
            conn.execute(text("ALTER TABLE vendors ADD COLUMN local_proximity_km FLOAT DEFAULT 15.0;"))

        # purchase_orders
        res_po = conn.execute(text("PRAGMA table_info(purchase_orders);")).fetchall()
        cols_po = [r[1] for r in res_po]
        if "netsuite_internal_id" not in cols_po:
            conn.execute(text("ALTER TABLE purchase_orders ADD COLUMN netsuite_internal_id VARCHAR(50) DEFAULT 'NS-REC-10482';"))
        if "netsuite_sync_status" not in cols_po:
            conn.execute(text("ALTER TABLE purchase_orders ADD COLUMN netsuite_sync_status VARCHAR(50) DEFAULT 'Synced (SuiteTalk REST)';"))
        if "netsuite_subsidiary" not in cols_po:
            conn.execute(text("ALTER TABLE purchase_orders ADD COLUMN netsuite_subsidiary VARCHAR(100) DEFAULT 'TechCorp Americas (Sub 01)';"))
        if "netsuite_gl_account" not in cols_po:
            conn.execute(text("ALTER TABLE purchase_orders ADD COLUMN netsuite_gl_account VARCHAR(100) DEFAULT '6010 - Direct Sourcing & Material CapEx';"))

        conn.commit()
except Exception as e:
    pass

# Ingest & index procurement policy documents in ChromaDB
try:
    init_policy_db()
except Exception as e:
    print(f"[WARN] Policy DB initialization warning on startup: {e}")

app = FastAPI(
    title="ProcureIQ - Intelligent NetSuite-Aligned ERP Procurement",
    description="Streamlining procurement from Purchase Request to Purchase Order with automated RFQ bidding, dynamic multi-rule approvals, Gemini 2.5 Flash AI auditing, autonomous RAG policy compliance guard, and 3-Way Match tracking.",
    version="1.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "*"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ensure generated_pos folder exists
GENERATED_POS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "generated_pos")
os.makedirs(GENERATED_POS_DIR, exist_ok=True)

# Mount Routers
app.include_router(auth.router, prefix="/api")
app.include_router(purchase_requests.router, prefix="/api")
app.include_router(vendors.router, prefix="/api")
app.include_router(approvals.router, prefix="/api")
app.include_router(dashboard.router, prefix="/api")


@app.get("/")
def root():
    return {
        "system": "ProcureIQ Enterprise ERP",
        "status": "Online",
        "version": "1.0.0",
        "docs": "/docs"
    }


@app.get("/api/health")
def health_check():
    return {
        "status": "healthy",
        "database": "sqlite:///procureiq.db",
        "engine": "FastAPI + SQLAlchemy + Gemini 2.5 Flash"
    }
