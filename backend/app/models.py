import datetime

from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    Text,
    DateTime,
    Boolean,
    ForeignKey,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False)
    role = Column(String(100), nullable=False)
    department = Column(String(100), nullable=False)

    purchase_requests = relationship(
        "PurchaseRequest",
        back_populates="requester",
        foreign_keys="PurchaseRequest.requester_id",
    )
    approvals = relationship(
        "ApprovalWorkflow",
        back_populates="approver",
        foreign_keys="ApprovalWorkflow.approver_id",
    )


class Vendor(Base):
    __tablename__ = "vendors"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    contact_email = Column(String(255), nullable=False)
    phone = Column(String(50), nullable=False)
    avg_delivery_days = Column(Integer, default=5, nullable=False)
    reliability_score = Column(Float, default=90.0, nullable=False)
    pricing_tier = Column(String(50), nullable=False)
    specialties = Column(Text, nullable=True)
    status = Column(String(50), default="Active", nullable=False)
    is_local_vendor = Column(Boolean, default=False, nullable=True)
    is_incubator = Column(Boolean, default=False, nullable=True)
    local_proximity_km = Column(Float, default=15.0, nullable=True)

    bids = relationship(
        "VendorBid",
        back_populates="vendor",
        cascade="all, delete-orphan",
    )
    performances = relationship(
        "VendorPerformance",
        back_populates="vendor",
        cascade="all, delete-orphan",
    )
    purchase_orders = relationship("PurchaseOrder", back_populates="vendor")


class PurchaseRequest(Base):
    __tablename__ = "purchase_requests"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    item_description = Column(Text, nullable=False)
    quantity = Column(Integer, default=1, nullable=False)
    urgency = Column(String(50), default="Medium", nullable=False)
    status = Column(String(50), default="Pending Approval", nullable=False)
    requester_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    department = Column(String(100), nullable=False)
    estimated_budget = Column(Float, default=0.0, nullable=False)
    created_at = Column(
        DateTime,
        default=datetime.datetime.utcnow,
        nullable=False,
    )

    requester = relationship(
        "User",
        back_populates="purchase_requests",
        foreign_keys=[requester_id],
    )
    bids = relationship(
        "VendorBid",
        back_populates="purchase_request",
        cascade="all, delete-orphan",
    )
    approval_workflows = relationship(
        "ApprovalWorkflow",
        back_populates="purchase_request",
        cascade="all, delete-orphan",
    )
    purchase_order = relationship(
        "PurchaseOrder",
        back_populates="purchase_request",
        uselist=False,
    )
    compliance_check = relationship(
        "ComplianceCheck",
        back_populates="purchase_request",
        uselist=False,
        cascade="all, delete-orphan",
    )


class VendorBid(Base):
    __tablename__ = "vendor_bids"

    id = Column(Integer, primary_key=True, index=True)
    vendor_id = Column(Integer, ForeignKey("vendors.id"), nullable=False)
    pr_id = Column(Integer, ForeignKey("purchase_requests.id"), nullable=False)
    quoted_price = Column(Float, nullable=False)
    original_quoted_price = Column(Float, nullable=True)
    delivery_days = Column(Integer, nullable=False)
    original_delivery_days = Column(Integer, nullable=True)
    notes = Column(Text, nullable=True)
    bid_score = Column(Float, default=0.0, nullable=False)
    negotiation_transcript = Column(Text, nullable=True)

    vendor = relationship("Vendor", back_populates="bids")
    purchase_request = relationship("PurchaseRequest", back_populates="bids")
    negotiation_sessions = relationship(
        "NegotiationSession",
        back_populates="vendor_bid",
        cascade="all, delete-orphan",
        order_by="NegotiationSession.session_number",
    )


class ApprovalWorkflow(Base):
    __tablename__ = "approval_workflows"

    id = Column(Integer, primary_key=True, index=True)
    pr_id = Column(Integer, ForeignKey("purchase_requests.id"), nullable=False)
    approver_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    triggered_rule = Column(String(255), nullable=False)
    status = Column(String(50), default="Pending", nullable=False)
    comment = Column(Text, nullable=True)
    created_at = Column(
        DateTime,
        default=datetime.datetime.utcnow,
        nullable=False,
    )
    actioned_at = Column(DateTime, nullable=True)

    purchase_request = relationship(
        "PurchaseRequest",
        back_populates="approval_workflows",
    )
    approver = relationship(
        "User",
        back_populates="approvals",
        foreign_keys=[approver_id],
    )


class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"

    id = Column(Integer, primary_key=True, index=True)
    pr_id = Column(Integer, ForeignKey("purchase_requests.id"), nullable=False)
    vendor_id = Column(Integer, ForeignKey("vendors.id"), nullable=False)
    po_number = Column(String(100), unique=True, index=True, nullable=False)
    total_amount = Column(Float, nullable=False)
    status = Column(String(50), default="Sent", nullable=False)
    pdf_url = Column(String(255), nullable=False)
    netsuite_internal_id = Column(
        String(50),
        default="NS-REC-10482",
        nullable=True,
    )
    netsuite_sync_status = Column(
        String(50),
        default="Synced (SuiteTalk REST)",
        nullable=True,
    )
    netsuite_subsidiary = Column(
        String(100),
        default="TechCorp Americas (Sub 01)",
        nullable=True,
    )
    netsuite_gl_account = Column(
        String(100),
        default="6010 - Direct Sourcing & Material CapEx",
        nullable=True,
    )
    created_at = Column(
        DateTime,
        default=datetime.datetime.utcnow,
        nullable=False,
    )

    purchase_request = relationship(
        "PurchaseRequest",
        back_populates="purchase_order",
    )
    vendor = relationship("Vendor", back_populates="purchase_orders")


class VendorPerformance(Base):
    __tablename__ = "vendor_performances"

    id = Column(Integer, primary_key=True, index=True)
    vendor_id = Column(Integer, ForeignKey("vendors.id"), nullable=False)
    metric_type = Column(String(50), nullable=False)
    value = Column(Float, nullable=False)
    recorded_at = Column(
        DateTime,
        default=datetime.datetime.utcnow,
        nullable=False,
    )
    notes = Column(Text, nullable=True)

    vendor = relationship("Vendor", back_populates="performances")


class ComplianceCheck(Base):
    __tablename__ = "compliance_checks"

    id = Column(Integer, primary_key=True, index=True)
    pr_id = Column(
        Integer,
        ForeignKey("purchase_requests.id"),
        unique=True,
        nullable=False,
    )
    compliant = Column(Boolean, default=True, nullable=False)
    violations_json = Column(Text, default="[]", nullable=False)
    required_action = Column(Text, default="", nullable=False)
    checked_at = Column(
        DateTime,
        default=datetime.datetime.utcnow,
        nullable=False,
    )

    purchase_request = relationship(
        "PurchaseRequest",
        back_populates="compliance_check",
    )


class NegotiationSession(Base):
    __tablename__ = "negotiation_sessions"

    id = Column(Integer, primary_key=True, index=True)
    vendor_bid_id = Column(
        Integer,
        ForeignKey("vendor_bids.id"),
        nullable=False,
        index=True,
    )
    session_number = Column(Integer, nullable=False)
    status = Column(
        String(50),
        default="INITIATED",
        nullable=False,
        index=True,
    )
    current_round = Column(Integer, default=0, nullable=False)
    current_price = Column(Float, nullable=False)
    current_delivery_days = Column(Integer, nullable=False)
    price_ceiling = Column(Float, nullable=False)
    delivery_floor = Column(Integer, nullable=False)
    created_at = Column(
        DateTime,
        default=datetime.datetime.utcnow,
        nullable=False,
    )
    updated_at = Column(
        DateTime,
        default=datetime.datetime.utcnow,
        onupdate=datetime.datetime.utcnow,
        nullable=False,
    )

    vendor_bid = relationship(
        "VendorBid",
        back_populates="negotiation_sessions",
    )

    __table_args__ = (
        UniqueConstraint(
            "vendor_bid_id",
            "session_number",
            name="uq_negotiation_session_bid_number",
        ),
    )