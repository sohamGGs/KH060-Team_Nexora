import os
import datetime

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app import models
from app.database import Base, engine
from app.routers import auth, purchase_requests, vendors, approvals, dashboard
from app.compliance.ingest import init_policy_db

Base.metadata.create_all(bind=engine)

with engine.connect() as conn:
    patches = {
        "vendor_bids": [
            ("original_quoted_price", "FLOAT"),
            ("original_delivery_days", "INTEGER"),
            ("negotiation_transcript", "TEXT"),
        ],
        "vendors": [
            ("is_local_vendor", "BOOLEAN"),
            ("is_incubator", "BOOLEAN"),
            ("local_proximity_km", "FLOAT"),
        ],
        "purchase_orders": [
            ("netsuite_internal_id", "VARCHAR(50)"),
            ("netsuite_sync_status", "VARCHAR(50)"),
            ("netsuite_subsidiary", "VARCHAR(100)"),
            ("netsuite_gl_account", "VARCHAR(100)"),
        ],
    }

    for table_name, columns in patches.items():
        try:
            result = conn.execute(text(f"PRAGMA table_info({table_name});")).fetchall()
            existing_columns = {row[1] for row in result}

            for column_name, column_type in columns:
                if column_name not in existing_columns:
                    conn.execute(
                        text(
                            f"ALTER TABLE {table_name} "
                            f"ADD COLUMN {column_name} {column_type};"
                        )
                    )
        except Exception:
            pass

    conn.commit()

try:
    init_policy_db()
except Exception:
    pass

app = FastAPI(
    title="ProcureIQ - Intelligent NetSuite-Aligned ERP Procurement",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(
    purchase_requests.router,
    prefix="/api/purchase-requests",
    tags=["Purchase Requests"],
)
app.include_router(vendors.router, prefix="/api/vendors", tags=["Vendors"])
app.include_router(approvals.router, prefix="/api/approvals", tags=["Approvals"])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["Dashboard"])

os.makedirs("generated_pos", exist_ok=True)


@app.get("/api/health")
def health_check():
    return {
        "status": "healthy",
        "system": "ProcureIQ Enterprise ERP",
        "database": "sqlite:///procureiq.db",
        "timestamp": datetime.datetime.utcnow().isoformat(),
    }