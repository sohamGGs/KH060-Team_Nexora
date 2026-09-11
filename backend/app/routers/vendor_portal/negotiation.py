from fastapi import APIRouter, Depends, HTTPException
from typing import List, Optional, Any, Dict
from sqlalchemy.orm import Session
from datetime import datetime
from pydantic import BaseModel

from app.auth import require_vendor_role, get_current_user
from app.database import get_db
from app import models

router = APIRouter(dependencies=[Depends(require_vendor_role)])


class PublicNegotiationEvent(BaseModel):
    id: int
    round: int
    speaker_role: str
    event_type: str
    price: Optional[float] = None
    delivery_days: Optional[int] = None
    message: Optional[str] = None
    created_at: datetime


class VendorNegotiationSessionOut(BaseModel):
    session_id: int
    pr_id: int
    pr_title: str
    vendor_id: int
    vendor_name: str
    status: str
    current_round: int
    current_price: float
    current_delivery_days: int
    events: List[PublicNegotiationEvent] = []
    created_at: datetime
    updated_at: datetime


@router.get("", response_model=List[VendorNegotiationSessionOut])
@router.get("/", response_model=List[VendorNegotiationSessionOut])
def get_vendor_negotiations(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    vendor = db.query(models.Vendor).filter(models.Vendor.name == current_user.department).first()
    if not vendor:
        vendor = db.query(models.Vendor).first()
    if not vendor:
        return []

    sessions = (
        db.query(models.NegotiationSession)
        .join(models.VendorBid)
        .filter(models.VendorBid.vendor_id == vendor.id)
        .order_by(models.NegotiationSession.id.desc())
        .all()
    )

    out = []
    for s in sessions:
        bid = s.vendor_bid
        pr = bid.purchase_request if bid else None

        events_out = [
            PublicNegotiationEvent(
                id=ev.id,
                round=ev.round,
                speaker_role=ev.speaker_role,
                event_type=ev.event_type,
                price=ev.price,
                delivery_days=ev.delivery_days,
                message=ev.message,
                created_at=ev.created_at,
            )
            for ev in s.events
        ]

        out.append(
            VendorNegotiationSessionOut(
                session_id=s.id,
                pr_id=bid.pr_id if bid else 0,
                pr_title=pr.title if pr else f"PR-{bid.pr_id if bid else 0}",
                vendor_id=vendor.id,
                vendor_name=vendor.name,
                status=s.status,
                current_round=s.current_round,
                current_price=s.current_price,
                current_delivery_days=s.current_delivery_days,
                events=events_out,
                created_at=s.created_at,
                updated_at=s.updated_at,
            )
        )
    return out


@router.get("/{session_id}", response_model=VendorNegotiationSessionOut)
def get_vendor_negotiation_detail(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    vendor = db.query(models.Vendor).filter(models.Vendor.name == current_user.department).first()
    if not vendor:
        vendor = db.query(models.Vendor).first()

    session = (
        db.query(models.NegotiationSession)
        .filter(models.NegotiationSession.id == session_id)
        .first()
    )
    if not session:
        raise HTTPException(status_code=404, detail="Negotiation session not found")

    bid = session.vendor_bid
    if vendor and bid and bid.vendor_id != vendor.id:
        raise HTTPException(status_code=403, detail="Access denied to this negotiation session")

    pr = bid.purchase_request if bid else None
    events_out = [
        PublicNegotiationEvent(
            id=ev.id,
            round=ev.round,
            speaker_role=ev.speaker_role,
            event_type=ev.event_type,
            price=ev.price,
            delivery_days=ev.delivery_days,
            message=ev.message,
            created_at=ev.created_at,
        )
        for ev in session.events
    ]

    return VendorNegotiationSessionOut(
        session_id=session.id,
        pr_id=bid.pr_id if bid else 0,
        pr_title=pr.title if pr else f"PR-{bid.pr_id if bid else 0}",
        vendor_id=bid.vendor_id if bid else 0,
        vendor_name=bid.vendor.name if bid and bid.vendor else "Vendor",
        status=session.status,
        current_round=session.current_round,
        current_price=session.current_price,
        current_delivery_days=session.current_delivery_days,
        events=events_out,
        created_at=session.created_at,
        updated_at=session.updated_at,
    )
