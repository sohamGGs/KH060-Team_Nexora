import json
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import require_gov_role
from app.database import get_db
from app.models import (
    GovNegotiationState,
    NegotiationEscalation,
    NegotiationEvent,
    NegotiationSession,
    PolicyDecision,
    PurchaseRequest,
    Vendor,
    VendorBid,
    VendorNegotiationState,
    VendorPerformance,
)
from app.negotiation.graph import run_bilateral_negotiation
from app.negotiation.state import GraphNegotiationState
from app.schemas import (
    NegotiationEscalationAction,
    NegotiationEventOut,
    NegotiationHistoryResponse,
    NegotiationResponse,
    RecommendationsResponse,
    ScoreBreakdown,
    VendorRecommendation,
    VendorNegotiationResultOut,
    VendorOut,
    VendorRecommendation,
)

logger = logging.getLogger("routers.vendors")

# Router prefix is "/vendors" so app.main can include it at /api/gov and /api without doubling
router = APIRouter(
    dependencies=[Depends(require_gov_role)],
    prefix="/vendors",
    tags=["Gov - Vendors"],
)


def calculate_bid_score(bid: VendorBid, vendor: Vendor, budget: float) -> float:
    price_score = 0.0
    reliability_score = max(0.0, min(100.0, float(vendor.reliability_score or 0)))

    if budget > 0:
        price_score = max(0.0, min(100.0, (budget / max(bid.quoted_price, 1)) * 100))
    else:
        price_score = max(0.0, min(100.0, 100 - (bid.quoted_price / max(bid.quoted_price, 1) * 50)))

    avg_days = vendor.avg_delivery_days or bid.delivery_days
    delivery_score = max(
        0.0,
        min(100.0, 100 - ((bid.delivery_days - avg_days) * 5)),
    )

    return round(
        price_score * 0.50
        + delivery_score * 0.20
        + reliability_score * 0.30,
        2,
    )


def compute_vendor_score(
    vendor: Vendor,
    quoted_price: float,
    bid_days: int,
    budget: float,
    performances: Optional[List[VendorPerformance]] = None,
) -> Dict[str, Any]:
    """
    Computes vendor score breakdown (out of 100).
    Preserves exact compatibility for dashboard and purchase-request callers.
    """
    safe_budget = max(budget, 1.0)
    price_variance_ratio = (quoted_price - safe_budget) / safe_budget
    raw_price_score = 30.0 * (1.0 - price_variance_ratio)
    price_score = min(30.0, max(0.0, raw_price_score))
    price_variance_pct = round(price_variance_ratio * 100.0, 2)

    avg_days = max(1, getattr(vendor, "avg_delivery_days", 1) or 1)
    raw_delivery_score = 25.0 * (1.0 - (bid_days - avg_days) / avg_days)
    delivery_score = min(25.0, max(5.0, raw_delivery_score))

    rel_score = float(getattr(vendor, "reliability_score", 0.0) or 0.0)
    rel_pct = max(0.0, min(100.0, rel_score))
    reliability_score = 25.0 * (rel_pct / 100.0)

    is_incubator = bool(getattr(vendor, "is_incubator", False) or getattr(vendor, "is_local_vendor", False))
    nearshoring_bonus = 0.0

    if performances:
        mean_perf = sum(p.value for p in performances) / len(performances)
    elif is_incubator:
        mean_perf = 80.0
        nearshoring_bonus = 3.0
    else:
        mean_perf = rel_score

    mean_perf = max(0.0, min(100.0, mean_perf))
    history_score = 20.0 * (mean_perf / 100.0)

    total_score = round(
        min(100.0, price_score + delivery_score + reliability_score + history_score + nearshoring_bonus),
        2,
    )

    history_score_raw = round(history_score * 5.0, 1)
    scores_dict = {
        "price_score": round(price_score, 1),
        "delivery_score": round(delivery_score, 1),
        "reliability_score": round(reliability_score, 1),
        "history_score": round(history_score, 1),
        "nearshoring_bonus": round(nearshoring_bonus, 1),
        "total_score": total_score,
        "price_variance_pct": price_variance_pct,
    }
    return {
        **scores_dict,
        "scores": scores_dict,
        "history_score_raw": history_score_raw,
    }


def build_recommendations(db: Session, pr: PurchaseRequest) -> List[VendorRecommendation]:
    bids = db.query(VendorBid).filter(VendorBid.pr_id == pr.id).all()
    recommendations = []

    for bid in bids:
        vendor = db.query(Vendor).filter(Vendor.id == bid.vendor_id).first()
        if not vendor:
            continue

        perfs = db.query(VendorPerformance).filter(VendorPerformance.vendor_id == vendor.id).all()
        scores = compute_vendor_score(
            vendor=vendor,
            quoted_price=bid.quoted_price,
            bid_days=bid.delivery_days,
            budget=pr.estimated_budget,
            performances=perfs,
        )

        history_raw = scores.get("history_score_raw", round(scores["history_score"] * 5.0, 1))

        transcript_list = None
        if getattr(bid, "negotiation_transcript", None):
            try:
                transcript_list = json.loads(bid.negotiation_transcript)
            except Exception:
                transcript_list = None

        recommendations.append(
            VendorRecommendation(
                bid_id=bid.id,
                vendor_id=vendor.id,
                vendor_name=vendor.name,
                pricing_tier=vendor.pricing_tier,
                contact_email=vendor.contact_email or "",
                quoted_price=bid.quoted_price,
                original_quoted_price=getattr(bid, "original_quoted_price", None),
                estimated_budget=pr.estimated_budget,
                delivery_days=bid.delivery_days,
                original_delivery_days=getattr(bid, "original_delivery_days", None),
                avg_delivery_days=vendor.avg_delivery_days,
                reliability_score=vendor.reliability_score or 0.0,
                history_score_raw=history_raw,
                notes=bid.notes,
                scores=ScoreBreakdown(**scores["scores"]),
                rank=0,
                bid_score=scores["total_score"],
                is_incubator=bool(getattr(vendor, "is_incubator", False)),
                is_local_vendor=bool(getattr(vendor, "is_local_vendor", False)),
                local_proximity_km=getattr(vendor, "local_proximity_km", 15.0),
                negotiation_transcript=transcript_list,
            )
        )

    recommendations.sort(key=lambda r: r.scores.total_score, reverse=True)
    for idx, rec in enumerate(recommendations, start=1):
        rec.rank = idx
    return recommendations


@router.get("", response_model=List[VendorOut])
def get_vendors(db: Session = Depends(get_db)):
    return db.query(Vendor).all()


@router.get("/recommendations/{pr_id}", response_model=RecommendationsResponse)
def get_vendor_recommendations(
    pr_id: int,
    db: Session = Depends(get_db),
):
    pr = db.query(PurchaseRequest).filter(PurchaseRequest.id == pr_id).first()
    if not pr:
        raise HTTPException(status_code=404, detail="Purchase request not found")

    recommendations = build_recommendations(db, pr)
    return RecommendationsResponse(
        pr_id=pr.id,
        pr_title=pr.title,
        estimated_budget=pr.estimated_budget,
        urgency=pr.urgency,
        department=pr.department,
        recommendations=recommendations,
    )


@router.post("/negotiate/{pr_id}", response_model=NegotiationResponse)
def run_autonomous_negotiation_endpoint(
    pr_id: int,
    db: Session = Depends(get_db),
):
    pr = db.query(PurchaseRequest).filter(PurchaseRequest.id == pr_id).first()
    if not pr:
        raise HTTPException(status_code=404, detail="Purchase request not found")

    bids = (
        db.query(VendorBid)
        .filter(VendorBid.pr_id == pr_id)
        .order_by(VendorBid.bid_score.desc())
        .all()
    )
    if not bids:
        raise HTTPException(status_code=404, detail="No vendor bids found")

    candidates = []
    for bid in bids:
        active_session = (
            db.query(NegotiationSession)
            .filter(
                NegotiationSession.vendor_bid_id == bid.id,
                NegotiationSession.status.in_(
                    ["INITIATED", "NEGOTIATING", "ESCALATED", "PENDING_APPROVAL", "RESUMED"]
                ),
            )
            .first()
        )
        if active_session:
            continue

        vendor = db.query(Vendor).filter(Vendor.id == bid.vendor_id).first()
        if not vendor:
            continue

        candidates.append((bid, vendor))
        if len(candidates) == 3:
            break

    if not candidates:
        raise HTTPException(
            status_code=409,
            detail="All eligible vendor bids already have active negotiation sessions",
        )

    results: List[VendorNegotiationResultOut] = []
    sessions: List[NegotiationSession] = []
    any_escalated = False
    all_completed = True

    total_initial_spend = 0.0
    total_negotiated_spend = 0.0

    for bid, vendor in candidates:
        if bid.original_quoted_price is None:
            bid.original_quoted_price = bid.quoted_price
        if bid.original_delivery_days is None:
            bid.original_delivery_days = bid.delivery_days

        session_count = (
            db.query(NegotiationSession)
            .filter(NegotiationSession.vendor_bid_id == bid.id)
            .count()
        )

        # 1. Persist NegotiationSession using only existing models.py fields
        session = NegotiationSession(
            vendor_bid_id=bid.id,
            session_number=session_count + 1,
            status="INITIATED",
            current_round=0,
            current_price=bid.quoted_price,
            current_delivery_days=bid.delivery_days,
            version=1,
        )
        db.add(session)
        db.flush()

        # 2. Persist GovNegotiationState
        budget = float(pr.estimated_budget)
        gov_target = round(min(float(bid.quoted_price) * 0.85, budget * 0.95), 2)
        gov_max = budget
        gov_target_days = max(1, int(bid.delivery_days) - 3)
        gov_max_days = int(bid.delivery_days) + 5

        gov_state_record = GovNegotiationState(
            negotiation_session_id=session.id,
            target_price=gov_target,
            max_authorized_price=gov_max,
            target_delivery=gov_target_days,
            max_delivery=gov_max_days,
            strategy="Maximize cost savings within department budget ceiling",
        )
        db.add(gov_state_record)

        # 3. Persist VendorNegotiationState
        vendor_target = float(bid.quoted_price)
        vendor_floor = round(float(bid.quoted_price) * 0.80, 2)
        vendor_fastest = max(1, int(vendor.avg_delivery_days or bid.delivery_days))

        vendor_state_record = VendorNegotiationState(
            negotiation_session_id=session.id,
            target_price=vendor_target,
            absolute_minimum_price=vendor_floor,
            feasible_delivery=vendor_fastest,
            strategy="Protect profit margin and guarantee feasible delivery timeline",
        )
        db.add(vendor_state_record)
        db.flush()

        # 4. Construct bilateral graph state
        initial_state: GraphNegotiationState = {
            "shared": {
                "session_id": session.id,
                "pr_id": pr.id,
                "pr_title": pr.title,
                "item_description": pr.item_description or "",
                "quantity": pr.quantity,
                "current_round": 0,
                "status": "INITIATED",
                "events": [],
            },
            "gov": {
                "target_price": gov_target,
                "max_authorized_price": gov_max,
                "target_delivery": gov_target_days,
                "max_delivery": gov_max_days,
                "strategy": gov_state_record.strategy,
            },
            "vendor": {
                "target_price": vendor_target,
                "absolute_minimum_price": vendor_floor,
                "feasible_delivery": vendor_fastest,
                "strategy": vendor_state_record.strategy,
            },
            "next_actor": "GOV_AGENT",
        }

        # 5. Execute LangGraph bilateral negotiation
        final_state = run_bilateral_negotiation(initial_state)

        # 6. Persist NegotiationEvent records with exact model fields
        event_outs: List[NegotiationEventOut] = []
        last_price = float(bid.quoted_price)
        last_days = int(bid.delivery_days)

        for ev in final_state["shared"]["events"]:
            ev_price = ev.get("price")
            ev_days = ev.get("delivery_days")
            if ev_price is not None:
                last_price = float(ev_price)
            if ev_days is not None:
                last_days = int(ev_days)

            event_record = NegotiationEvent(
                negotiation_session_id=session.id,
                round=int(ev.get("round", 0)),
                speaker_role=str(ev.get("speaker_role", "SYSTEM")),
                event_type=str(ev.get("event_type", "OFFER")),
                price=float(ev_price) if ev_price is not None else None,
                delivery_days=int(ev_days) if ev_days is not None else None,
                message=str(ev.get("message", "")),
            )
            db.add(event_record)
            db.flush()

            event_outs.append(
                NegotiationEventOut(
                    id=event_record.id,
                    round=event_record.round,
                    speaker_role=event_record.speaker_role,
                    event_type=event_record.event_type,
                    price=event_record.price,
                    delivery_days=event_record.delivery_days,
                    message=event_record.message,
                    created_at=event_record.created_at,
                )
            )

        # 7. Update session status and record policy decisions
        raw_status = final_state["shared"].get("status", "NEGOTIATING")
        if raw_status in ["ACCEPTED", "ACCEPT"]:
            final_status = "ACCEPTED"
            action = "ACCEPT"
        elif raw_status in ["ESCALATED", "ESCALATE"]:
            final_status = "PENDING_APPROVAL"
            action = "ESCALATE"
        elif raw_status in ["REJECTED", "REJECT"]:
            final_status = "REJECTED"
            action = "REJECT"
        else:
            final_status = "NEGOTIATING"
            action = "CONTINUE"

        session.status = final_status
        session.current_round = final_state["shared"].get("current_round", 0)
        session.current_price = last_price
        session.current_delivery_days = last_days

        policy_decision = PolicyDecision(
            negotiation_session_id=session.id,
            role="GOVERNMENT",
            round=session.current_round,
            evaluated_price=last_price,
            evaluated_delivery_days=last_days,
            decision=action,
            rule_triggered=f"Bilateral policy outcome: {final_status}",
            threshold_value=str(gov_max),
            actual_value=str(last_price),
        )
        db.add(policy_decision)

        escalation_id = None
        if action == "ESCALATE":
            any_escalated = True
            all_completed = False
            escalation = NegotiationEscalation(
                negotiation_session_id=session.id,
                role="GOVERNMENT",
                reason=f"Negotiation proposal of ${last_price:,.2f} requires management escalation.",
                requested_price=last_price,
                requested_delivery_days=last_days,
                status="PENDING",
            )
            db.add(escalation)
            db.flush()
            escalation_id = escalation.id
        elif action == "ACCEPT":
            bid.quoted_price = last_price
            bid.delivery_days = last_days
            bid.bid_score = calculate_bid_score(bid, vendor, pr.estimated_budget)
        elif action == "CONTINUE":
            all_completed = False

        initial_p = float(bid.original_quoted_price)
        savings = max(0.0, initial_p - float(last_price))
        savings_pct = (savings / initial_p * 100.0) if initial_p > 0 else 0.0

        total_initial_spend += initial_p
        total_negotiated_spend += float(last_price)

        results.append(
            VendorNegotiationResultOut(
                vendor_id=vendor.id,
                vendor_name=vendor.name,
                final_price=round(last_price, 2),
                final_days=int(last_days),
                savings=round(savings, 2),
                savings_percentage=round(savings_pct, 2),
                status=session.status,
                action=action,
                is_fallback=False,
                events=event_outs,
                session_id=session.id,
                escalation_id=escalation_id,
            )
        )
        sessions.append(session)

    db.commit()

    total_net_savings = max(0.0, total_initial_spend - total_negotiated_spend)
    total_savings_pct = (total_net_savings / total_initial_spend * 100.0) if total_initial_spend > 0 else 0.0

    # Determine top vendor from updated recommendations
    fresh_recs = build_recommendations(db, pr)
    top_v_id = fresh_recs[0].vendor_id if fresh_recs else None
    top_v_name = fresh_recs[0].vendor_name if fresh_recs else None

    return NegotiationResponse(
        pr_id=pr.id,
        pr_title=pr.title,
        estimated_budget=pr.estimated_budget,
        total_initial_spend=round(total_initial_spend, 2),
        total_negotiated_spend=round(total_negotiated_spend, 2),
        total_savings=round(total_net_savings, 2),
        total_savings_pct=round(total_savings_pct, 2),
        top_vendor_id=top_v_id,
        top_vendor_name=top_v_name,
        results=results,
        recommendations=fresh_recs,
        completed=all_completed and not any_escalated,
        escalated=any_escalated,
        sessions=sessions,
    )


@router.get(
    "/negotiation/{session_id}",
    response_model=NegotiationHistoryResponse,
)
def get_negotiation_history(
    session_id: int,
    db: Session = Depends(get_db),
):
    session = (
        db.query(NegotiationSession)
        .filter(NegotiationSession.id == session_id)
        .first()
    )
    if not session:
        raise HTTPException(status_code=404, detail="Negotiation session not found")

    gov_state = (
        db.query(GovNegotiationState)
        .filter(GovNegotiationState.negotiation_session_id == session.id)
        .first()
    )

    events = (
        db.query(NegotiationEvent)
        .filter(NegotiationEvent.negotiation_session_id == session.id)
        .order_by(NegotiationEvent.round.asc(), NegotiationEvent.id.asc())
        .all()
    )

    decisions = (
        db.query(PolicyDecision)
        .filter(PolicyDecision.negotiation_session_id == session.id)
        .order_by(PolicyDecision.round.asc())
        .all()
    )

    escalations = (
        db.query(NegotiationEscalation)
        .filter(NegotiationEscalation.negotiation_session_id == session.id)
        .all()
    )

    return NegotiationHistoryResponse(
        session=session,
        gov_state=gov_state,
        events=events,
        decisions=decisions,
        escalations=escalations,
    )


@router.post(
    "/negotiation/{session_id}/escalation",
)
def action_negotiation_escalation(
    session_id: int,
    action: NegotiationEscalationAction,
    db: Session = Depends(get_db),
):
    session = (
        db.query(NegotiationSession)
        .filter(NegotiationSession.id == session_id)
        .first()
    )
    if not session:
        raise HTTPException(status_code=404, detail="Negotiation session not found")

    escalation = (
        db.query(NegotiationEscalation)
        .filter(NegotiationEscalation.negotiation_session_id == session_id)
        .order_by(NegotiationEscalation.id.desc())
        .first()
    )
    if not escalation:
        raise HTTPException(status_code=404, detail="No escalation found for this session")

    if action.decision == "APPROVE":
        escalation.status = "APPROVED"
        session.status = "RESUMED"
    else:
        escalation.status = "REJECTED"
        session.status = "REJECTED"

    escalation.comment = action.comment
    escalation.actioned_at = datetime.utcnow()
    db.commit()

    return {
        "session_id": session.id,
        "escalation_id": escalation.id,
        "status": escalation.status,
        "message": f"Negotiation escalation {action.decision.lower()}ed",
    }


@router.post(
    "/negotiation/{session_id}/resume",
    response_model=NegotiationResponse,
)
def resume_negotiation_endpoint(
    session_id: int,
    db: Session = Depends(get_db),
):
    session = (
        db.query(NegotiationSession)
        .filter(NegotiationSession.id == session_id)
        .first()
    )
    if not session:
        raise HTTPException(status_code=404, detail="Negotiation session not found")

    escalation = (
        db.query(NegotiationEscalation)
        .filter(
            NegotiationEscalation.negotiation_session_id == session_id,
            NegotiationEscalation.status == "APPROVED",
        )
        .order_by(NegotiationEscalation.id.desc())
        .first()
    )
    if not escalation:
        raise HTTPException(
            status_code=400,
            detail="Negotiation cannot resume without an approved escalation",
        )

    bid = db.query(VendorBid).filter(VendorBid.id == session.vendor_bid_id).first()
    pr = db.query(PurchaseRequest).filter(PurchaseRequest.id == bid.pr_id).first()
    vendor = db.query(Vendor).filter(Vendor.id == bid.vendor_id).first()

    gov_state_rec = (
        db.query(GovNegotiationState)
        .filter(GovNegotiationState.negotiation_session_id == session.id)
        .first()
    )
    vendor_state_rec = (
        db.query(VendorNegotiationState)
        .filter(VendorNegotiationState.negotiation_session_id == session.id)
        .first()
    )

    # Reconstruct previous events
    existing_events = (
        db.query(NegotiationEvent)
        .filter(NegotiationEvent.negotiation_session_id == session.id)
        .order_by(NegotiationEvent.round.asc(), NegotiationEvent.id.asc())
        .all()
    )

    events_list = [
        {
            "round": e.round,
            "speaker_role": e.speaker_role,
            "event_type": e.event_type,
            "price": e.price,
            "delivery_days": e.delivery_days,
            "message": e.message,
        }
        for e in existing_events
    ]

    initial_state: GraphNegotiationState = {
        "shared": {
            "session_id": session.id,
            "pr_id": pr.id,
            "pr_title": pr.title,
            "item_description": pr.item_description or "",
            "quantity": pr.quantity,
            "current_round": session.current_round + 1,
            "status": "RESUMED",
            "events": events_list,
        },
        "gov": {
            "target_price": gov_state_rec.target_price if gov_state_rec else float(session.current_price),
            "max_authorized_price": float(escalation.requested_price or pr.estimated_budget),
            "target_delivery": gov_state_rec.target_delivery if gov_state_rec else int(session.current_delivery_days),
            "max_delivery": gov_state_rec.max_delivery if gov_state_rec else int(session.current_delivery_days) + 5,
            "strategy": "Supervisory approval granted. Conclude agreement within approved limits.",
        },
        "vendor": {
            "target_price": vendor_state_rec.target_price if vendor_state_rec else float(session.current_price),
            "absolute_minimum_price": vendor_state_rec.absolute_minimum_price if vendor_state_rec else float(session.current_price) * 0.85,
            "feasible_delivery": vendor_state_rec.feasible_delivery if vendor_state_rec else int(session.current_delivery_days),
            "strategy": "Conclude agreement reliably.",
        },
        "next_actor": "GOV_AGENT",
    }

    final_state = run_bilateral_negotiation(initial_state)

    # Save newly generated events
    event_outs: List[NegotiationEventOut] = []
    last_price = float(session.current_price)
    last_days = int(session.current_delivery_days)

    new_events = final_state["shared"]["events"][len(existing_events):]
    for ev in new_events:
        ev_price = ev.get("price")
        ev_days = ev.get("delivery_days")
        if ev_price is not None:
            last_price = float(ev_price)
        if ev_days is not None:
            last_days = int(ev_days)

        event_rec = NegotiationEvent(
            negotiation_session_id=session.id,
            round=int(ev.get("round", session.current_round + 1)),
            speaker_role=str(ev.get("speaker_role", "SYSTEM")),
            event_type=str(ev.get("event_type", "OFFER")),
            price=float(ev_price) if ev_price is not None else None,
            delivery_days=int(ev_days) if ev_days is not None else None,
            message=str(ev.get("message", "")),
        )
        db.add(event_rec)
        db.flush()

        event_outs.append(
            NegotiationEventOut(
                id=event_rec.id,
                round=event_rec.round,
                speaker_role=event_rec.speaker_role,
                event_type=event_rec.event_type,
                price=event_rec.price,
                delivery_days=event_rec.delivery_days,
                message=event_rec.message,
                created_at=event_rec.created_at,
            )
        )

    raw_status = final_state["shared"].get("status", "ACCEPTED")
    if raw_status in ["ACCEPTED", "ACCEPT"]:
        final_status = "ACCEPTED"
        action = "ACCEPT"
        bid.quoted_price = last_price
        bid.delivery_days = last_days
        bid.bid_score = calculate_bid_score(bid, vendor, pr.estimated_budget)
    elif raw_status in ["ESCALATED", "ESCALATE"]:
        final_status = "PENDING_APPROVAL"
        action = "ESCALATE"
    else:
        final_status = "REJECTED"
        action = "REJECT"

    session.status = final_status
    session.current_round = final_state["shared"].get("current_round", session.current_round + 1)
    session.current_price = last_price
    session.current_delivery_days = last_days

    policy_decision = PolicyDecision(
        negotiation_session_id=session.id,
        role="GOVERNMENT",
        round=session.current_round,
        evaluated_price=last_price,
        evaluated_delivery_days=last_days,
        decision=action,
        rule_triggered=f"Bilateral resumed outcome: {final_status}",
        threshold_value=str(escalation.requested_price),
        actual_value=str(last_price),
    )
    db.add(policy_decision)
    db.commit()

    initial_p = float(bid.original_quoted_price or bid.quoted_price)
    savings = max(0.0, initial_p - float(last_price))
    savings_pct = (savings / initial_p * 100.0) if initial_p > 0 else 0.0

    result_out = VendorNegotiationResultOut(
        vendor_id=vendor.id,
        vendor_name=vendor.name,
        final_price=round(last_price, 2),
        final_days=int(last_days),
        savings=round(savings, 2),
        savings_percentage=round(savings_pct, 2),
        status=session.status,
        action=action,
        is_fallback=False,
        events=event_outs,
        session_id=session.id,
        escalation_id=None,
    )

    fresh_recs = build_recommendations(db, pr)

    return NegotiationResponse(
        pr_id=pr.id,
        pr_title=pr.title,
        estimated_budget=pr.estimated_budget,
        total_initial_spend=round(initial_p, 2),
        total_negotiated_spend=round(last_price, 2),
        total_savings=round(savings, 2),
        total_savings_pct=round(savings_pct, 2),
        top_vendor_id=vendor.id,
        top_vendor_name=vendor.name,
        results=[result_out],
        recommendations=fresh_recs,
        completed=final_status == "ACCEPTED",
        escalated=final_status == "PENDING_APPROVAL",
        sessions=[session],
    )
