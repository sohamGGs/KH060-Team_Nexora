from typing import Any, Dict, List, Optional
import json
from datetime import datetime
from app.negotiation.agents import resume_negotiation
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import (
    NegotiationEscalation,
    NegotiationSession,
    PolicyDecision,
    PurchaseRequest,
    Vendor,
    VendorBid,
    VendorPerformance,
)
from app.negotiation.agents import run_multi_agent_negotiation
from app.schemas import (
    NegotiationHistoryResponse,
    NegotiationResponse,
    NegotiationTurnOut,
    NegotiationEscalationAction,
    VendorNegotiationResultOut,
    VendorOut,
    VendorRecommendation,
    RecommendationsResponse,
)

router = APIRouter(prefix="/api/vendors", tags=["vendors"])


def calculate_bid_score(bid: VendorBid, vendor: Vendor, budget: float) -> float:
    price_score = 0.0
    delivery_score = 0.0
    reliability_score = max(0.0, min(100.0, float(vendor.reliability_score or 0)))

    if budget > 0:
        price_score = max(0.0, min(100.0, (budget / max(bid.quoted_price, 1)) * 100))
    else:
        price_score = max(0.0, min(100.0, 100 - (bid.quoted_price / max(bid.quoted_price, 1) * 50)))

    delivery_score = max(
        0.0,
        min(100.0, 100 - ((bid.delivery_days - vendor.avg_delivery_days) * 5)),
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
    Computes vendor score breakdown (out of 100) = Price(30) + Delivery(25) + Reliability(25) + History(20) + Nearshoring/Incubator Bonus.
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

    return {
        "scores": {
            "price_score": round(price_score, 2),
            "delivery_score": round(delivery_score, 2),
            "reliability_score": round(reliability_score, 2),
            "history_score": round(history_score, 2),
            "nearshoring_bonus": round(nearshoring_bonus, 2),
            "total_score": total_score,
            "price_variance_pct": price_variance_pct,
        },
        "history_score_raw": round(mean_perf, 2),
    }



def build_recommendations(
    db: Session,
    pr: PurchaseRequest,
) -> list[VendorRecommendation]:
    bids = (
        db.query(VendorBid)
        .filter(VendorBid.pr_id == pr.id)
        .all()
    )

    recommendations = []

    for bid in bids:
        vendor = db.query(Vendor).filter(Vendor.id == bid.vendor_id).first()
        if not vendor:
            continue

        score = calculate_bid_score(bid, vendor, pr.estimated_budget)
        bid.bid_score = score

        original_price = bid.original_quoted_price or bid.quoted_price
        savings = max(0.0, original_price - bid.quoted_price)
        savings_pct = (savings / original_price * 100) if original_price else 0.0

        recommendations.append(
            VendorRecommendation(
                vendor_id=vendor.id,
                vendor_name=vendor.name,
                quoted_price=bid.quoted_price,
                delivery_days=bid.delivery_days,
                bid_score=score,
                price_savings=round(savings, 2),
                savings_percentage=round(savings_pct, 2),
                recommendation_reason=(
                    "Strong combined price, delivery and reliability profile."
                ),
                scores={
                    "price": round(
                        min(100.0, (pr.estimated_budget / max(bid.quoted_price, 1)) * 100)
                        if pr.estimated_budget
                        else 0.0,
                        2,
                    ),
                    "delivery": round(
                        max(
                            0.0,
                            min(
                                100.0,
                                100 - ((bid.delivery_days - vendor.avg_delivery_days) * 5),
                            ),
                        ),
                        2,
                    ),
                    "reliability": round(vendor.reliability_score, 2),
                },
            )
        )

    recommendations.sort(key=lambda item: item.bid_score, reverse=True)

    db.commit()
    return recommendations


@router.get("", response_model=list[VendorOut])
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

    payload = []

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

        payload.append(
            {
                "vendor_id": vendor.id,
                "vendor_name": vendor.name,
                "pricing_tier": vendor.pricing_tier,
                "initial_price": float(bid.quoted_price),
                "initial_days": int(bid.delivery_days),
                "avg_delivery_days": int(vendor.avg_delivery_days or bid.delivery_days),
                "session_number": session_count + 1,
                "vendor_bid_id": bid.id,
            }
        )

    db.commit()

    graph_result = run_multi_agent_negotiation(
        pr_id=pr.id,
        pr_title=pr.title,
        item_description=pr.item_description,
        quantity=pr.quantity,
        estimated_budget=pr.estimated_budget,
        urgency=pr.urgency,
        department=pr.department,
        vendors=payload,
    )

    results = []
    sessions = []
    any_escalated = False
    all_completed = True

    for vendor_state, source in zip(graph_result["vendors"], payload):
        bid = db.query(VendorBid).filter(VendorBid.id == source["vendor_bid_id"]).first()

        session = NegotiationSession(
            vendor_bid_id=bid.id,
            session_number=source["session_number"],
            status=vendor_state["status"],
            current_round=graph_result["current_round"],
            current_price=vendor_state["current_price"],
            current_delivery_days=vendor_state["current_days"],
            price_ceiling=pr.estimated_budget,
            delivery_floor=vendor_state["delivery_floor"],
        )

        db.add(session)
        db.flush()

        for turn in vendor_state["transcript"]:
            if turn["speaker_role"] != "SYSTEM":
                continue

        policy_decision = PolicyDecision(
            negotiation_session_id=session.id,
            round=graph_result["current_round"],
            evaluated_price=vendor_state["current_price"],
            evaluated_delivery_days=vendor_state["current_days"],
            decision=vendor_state["action"],
            rule_triggered=vendor_state["policy_reason"] or "Policy evaluation completed",
            threshold_value=str(pr.estimated_budget),
            actual_value=str(vendor_state["current_price"]),
        )

        db.add(policy_decision)

        escalation_id = None

        if vendor_state["action"] == "ESCALATE":
            any_escalated = True
            all_completed = False

            session.status = "PENDING_APPROVAL"

            escalation = NegotiationEscalation(
                negotiation_session_id=session.id,
                reason=vendor_state["policy_reason"],
                requested_price=vendor_state["current_price"],
                requested_delivery_days=vendor_state["current_days"],
                status="PENDING",
            )

            db.add(escalation)
            db.flush()

            escalation_id = escalation.id

        elif vendor_state["action"] == "CONTINUE":
            all_completed = False

        if bid:
            if vendor_state["action"] == "ACCEPT":
                bid.quoted_price = vendor_state["final_price"]
                bid.delivery_days = vendor_state["final_days"]

            bid.negotiation_transcript = json.dumps(
                vendor_state["transcript"],
                default=str,
            )
            bid.bid_score = calculate_bid_score(
                bid,
                db.query(Vendor).filter(Vendor.id == bid.vendor_id).first(),
                pr.estimated_budget,
            )

        savings = max(
            0.0,
            source["initial_price"] - vendor_state["final_price"],
        )

        savings_pct = (
            savings / source["initial_price"] * 100
            if source["initial_price"]
            else 0.0
        )

        results.append(
            VendorNegotiationResultOut(
                vendor_id=vendor_state["vendor_id"],
                vendor_name=vendor_state["vendor_name"],
                final_price=vendor_state["final_price"],
                final_days=vendor_state["final_days"],
                savings=round(savings, 2),
                savings_percentage=round(savings_pct, 2),
                status=vendor_state["status"],
                action=vendor_state["action"],
                is_fallback=vendor_state["is_fallback"],
                transcript=[
                    NegotiationTurnOut(**turn)
                    for turn in vendor_state["transcript"]
                ],
                session_id=session.id,
                escalation_id=escalation_id,
            )
        )

        sessions.append(session)

    db.commit()

    return NegotiationResponse(
        pr_id=pr.id,
        results=results,
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

    decisions = (
        db.query(PolicyDecision)
        .filter(PolicyDecision.negotiation_session_id == session.id)
        .order_by(PolicyDecision.round.asc())
        .all()
    )

    escalation = (
        db.query(NegotiationEscalation)
        .filter(NegotiationEscalation.negotiation_session_id == session.id)
        .first()
    )

    transcript: list[NegotiationTurnOut] = []

    if session.vendor_bid and session.vendor_bid.negotiation_transcript:
        try:
            transcript = [
                NegotiationTurnOut(**turn)
                for turn in json.loads(session.vendor_bid.negotiation_transcript)
            ]
        except Exception:
            transcript = []

    return NegotiationHistoryResponse(
        session=session,
        decisions=decisions,
        escalation=escalation,
        transcript=transcript,
    )


@router.post(
    "/negotiation/{session_id}/escalation",
    response_model=dict,
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
        .first()
    )

    if not escalation:
        raise HTTPException(status_code=404, detail="No escalation found")

    if escalation.status != "PENDING":
        raise HTTPException(status_code=409, detail="Escalation already actioned")

    escalation.status = action.decision
    escalation.comment = action.comment
    escalation.actioned_at = datetime.utcnow()

    if action.decision == "APPROVE":
        session.status = "RESUMED"
    else:
        session.status = "REJECTED"

    db.commit()

    return {
        "message": f"Negotiation escalation {action.decision.lower()}ed",
        "session_id": session.id,
        "status": session.status,
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
        .first()
    )

    if not escalation:
        raise HTTPException(
            status_code=409,
            detail="Negotiation cannot resume without an approved escalation",
        )

    bid = session.vendor_bid
    vendor = bid.vendor
    pr = bid.purchase_request

    try:
        transcript = json.loads(bid.negotiation_transcript or "[]")
    except Exception:
        transcript = []

    result = resume_negotiation(
        session={
            "current_price": session.current_price,
            "current_delivery_days": session.current_delivery_days,
            "current_round": session.current_round,
        },
        vendor={
            "id": vendor.id,
            "name": vendor.name,
            "pricing_tier": vendor.pricing_tier,
            "avg_delivery_days": vendor.avg_delivery_days,
        },
        pr={
            "id": pr.id,
            "title": pr.title,
            "item_description": pr.item_description,
            "quantity": pr.quantity,
            "estimated_budget": pr.estimated_budget,
            "urgency": pr.urgency,
            "department": pr.department,
        },
        transcript=transcript,
    )

    vendor_state = result["vendors"][0]

    session.status = (
        "PENDING_APPROVAL"
        if vendor_state["action"] == "ESCALATE"
        else vendor_state["status"]
    )
    session.current_round = result["current_round"]
    session.current_price = vendor_state["current_price"]
    session.current_delivery_days = vendor_state["current_days"]
    session.updated_at = datetime.utcnow()

    db.add(
        PolicyDecision(
            negotiation_session_id=session.id,
            round=result["current_round"],
            evaluated_price=vendor_state["current_price"],
            evaluated_delivery_days=vendor_state["current_days"],
            decision=vendor_state["action"],
            rule_triggered=vendor_state["policy_reason"],
            threshold_value=str(pr.estimated_budget),
            actual_value=str(vendor_state["current_price"]),
        )
    )

    escalation_id = None

    if vendor_state["action"] == "ESCALATE":
        escalation = NegotiationEscalation(
            negotiation_session_id=session.id,
            reason=vendor_state["policy_reason"],
            requested_price=vendor_state["current_price"],
            requested_delivery_days=vendor_state["current_days"],
            status="PENDING",
        )
        db.add(escalation)
        db.flush()
        escalation_id = escalation.id

    bid.negotiation_transcript = json.dumps(
        vendor_state["transcript"],
        default=str,
    )

    if vendor_state["action"] == "ACCEPT":
        bid.quoted_price = vendor_state["final_price"]
        bid.delivery_days = vendor_state["final_days"]

    db.commit()
    db.refresh(session)

    savings = max(
        0.0,
        (bid.original_quoted_price or bid.quoted_price) - vendor_state["final_price"],
    )

    original = bid.original_quoted_price or bid.quoted_price
    savings_pct = savings / original * 100 if original else 0.0

    return NegotiationResponse(
        pr_id=pr.id,
        results=[
            VendorNegotiationResultOut(
                vendor_id=vendor.id,
                vendor_name=vendor.name,
                final_price=vendor_state["final_price"],
                final_days=vendor_state["final_days"],
                savings=round(savings, 2),
                savings_percentage=round(savings_pct, 2),
                status=session.status,
                action=vendor_state["action"],
                is_fallback=vendor_state["is_fallback"],
                transcript=[
                    NegotiationTurnOut(**turn)
                    for turn in vendor_state["transcript"]
                ],
                session_id=session.id,
                escalation_id=escalation_id,
            )
        ],
        completed=vendor_state["action"] == "ACCEPT",
        escalated=vendor_state["action"] == "ESCALATE",
        sessions=[session],
    )