from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app import models, schemas, auth

router = APIRouter(prefix="/vendors", tags=["Vendors"])


def compute_vendor_score(
    vendor: models.Vendor,
    quoted_price: float,
    bid_days: int,
    budget: float,
    performances: List[models.VendorPerformance]
) -> Dict[str, Any]:
    """
    Computes total score (out of 100) = Price(30) + Delivery(25) + Reliability(25) + History(20) + Nearshoring/Incubator Bonus
    - Cold-Start / Local Incubator Policy:
      If a new local vendor has no historical orders, assigns a Bayesian Prior (80.0% baseline) + Nearshoring Bonus (+3.0 pts)
      rather than penalizing with 0 or excluding from RFQs.
    """
    # 1. Price Score (30 max)
    safe_budget = max(budget, 1.0)
    price_variance_ratio = (quoted_price - safe_budget) / safe_budget
    raw_price_score = 30.0 * (1.0 - price_variance_ratio)
    price_score = min(30.0, max(0.0, raw_price_score))
    price_variance_pct = round(price_variance_ratio * 100.0, 2)

    # 2. Delivery Score (25 max, 5 min)
    avg_days = max(1, vendor.avg_delivery_days)
    raw_delivery_score = 25.0 * (1.0 - (bid_days - avg_days) / avg_days)
    delivery_score = min(25.0, max(5.0, raw_delivery_score))

    # 3. Reliability Score (25 max)
    rel_pct = max(0.0, min(100.0, vendor.reliability_score))
    reliability_score = 25.0 * (rel_pct / 100.0)

    # 4. History Score (20 max) with Bayesian Cold-Start Adjustment
    is_incubator = bool(getattr(vendor, "is_incubator", False) or getattr(vendor, "is_local_vendor", False))
    nearshoring_bonus = 0.0

    if performances:
        mean_perf = sum(p.value for p in performances) / len(performances)
    elif is_incubator:
        # Bayesian prior: 80.0% benchmark score for new/local suppliers
        mean_perf = 80.0
        nearshoring_bonus = 3.0  # +3 pts local ESG & low-emission nearshoring credit
    else:
        mean_perf = vendor.reliability_score

    mean_perf = max(0.0, min(100.0, mean_perf))
    history_score = 20.0 * (mean_perf / 100.0)

    total_score = round(min(100.0, price_score + delivery_score + reliability_score + history_score + nearshoring_bonus), 2)

    return {
        "scores": {
            "price_score": round(price_score, 2),
            "delivery_score": round(delivery_score, 2),
            "reliability_score": round(reliability_score, 2),
            "history_score": round(history_score, 2),
            "nearshoring_bonus": round(nearshoring_bonus, 2),
            "total_score": total_score,
            "price_variance_pct": price_variance_pct
        },
        "history_score_raw": round(mean_perf, 2)
    }


@router.get("", response_model=List[schemas.VendorOut])
def get_vendors(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    vendors = db.query(models.Vendor).all()
    results = []
    for v in vendors:
        perf_avg = db.query(func.avg(models.VendorPerformance.value)).filter(
            models.VendorPerformance.vendor_id == v.id
        ).scalar()
        v_out = schemas.VendorOut.model_validate(v)
        v_out.avg_performance_score = round(float(perf_avg), 1) if perf_avg is not None else v.reliability_score
        results.append(v_out)
    return results


@router.get("/recommendations/{pr_id}", response_model=schemas.RecommendationsResponse)
def get_vendor_recommendations(
    pr_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    pr = db.query(models.PurchaseRequest).filter(models.PurchaseRequest.id == pr_id).first()
    if not pr:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Purchase request {pr_id} not found"
        )

    bids = db.query(models.VendorBid).filter(models.VendorBid.pr_id == pr.id).all()
    if not bids:
        return schemas.RecommendationsResponse(
            pr_id=pr.id,
            pr_title=pr.title,
            estimated_budget=pr.estimated_budget,
            urgency=pr.urgency,
            department=pr.department,
            recommendations=[]
        )

    recommendations: List[schemas.VendorRecommendation] = []

    for bid in bids:
        vendor = bid.vendor
        performances = db.query(models.VendorPerformance).filter(
            models.VendorPerformance.vendor_id == vendor.id
        ).all()

        score_res = compute_vendor_score(
            vendor=vendor,
            quoted_price=bid.quoted_price,
            bid_days=bid.delivery_days,
            budget=pr.estimated_budget,
            performances=performances
        )

        # Update bid score in DB if needed
        bid.bid_score = score_res["scores"]["total_score"]

        transcript_list = None
        if bid.negotiation_transcript:
            try:
                import json
                transcript_list = json.loads(bid.negotiation_transcript)
            except Exception:
                transcript_list = None

        rec = schemas.VendorRecommendation(
            bid_id=bid.id,
            vendor_id=vendor.id,
            vendor_name=vendor.name,
            pricing_tier=vendor.pricing_tier,
            contact_email=vendor.contact_email,
            quoted_price=bid.quoted_price,
            original_quoted_price=bid.original_quoted_price,
            estimated_budget=pr.estimated_budget,
            delivery_days=bid.delivery_days,
            original_delivery_days=bid.original_delivery_days,
            avg_delivery_days=vendor.avg_delivery_days,
            reliability_score=vendor.reliability_score,
            history_score_raw=score_res["history_score_raw"],
            notes=bid.notes,
            scores=schemas.ScoreBreakdown(**score_res["scores"]),
            rank=0,
            is_local_vendor=bool(getattr(vendor, "is_local_vendor", False)),
            is_incubator=bool(getattr(vendor, "is_incubator", False)),
            local_proximity_km=getattr(vendor, "local_proximity_km", 15.0),
            negotiation_transcript=transcript_list
        )
        recommendations.append(rec)

    db.commit()

    # Rank by total score descending
    recommendations.sort(key=lambda x: x.scores.total_score, reverse=True)
    for idx, rec in enumerate(recommendations, start=1):
        rec.rank = idx

    return schemas.RecommendationsResponse(
        pr_id=pr.id,
        pr_title=pr.title,
        estimated_budget=pr.estimated_budget,
        urgency=pr.urgency,
        department=pr.department,
        recommendations=recommendations
    )


@router.post("/negotiate/{pr_id}", response_model=schemas.NegotiationResponse)
def run_autonomous_negotiation_endpoint(
    pr_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    """
    Executes a 3-round LangGraph multi-agent autonomous negotiation across
    the top 3 scored vendors for the given PR. Updates prices, delivery SLAs,
    recalculates composite scores, and persists full transcripts.
    """
    import json
    from app.negotiation.agents import run_multi_agent_negotiation

    pr = db.query(models.PurchaseRequest).filter(models.PurchaseRequest.id == pr_id).first()
    if not pr:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Purchase request {pr_id} not found"
        )

    bids = db.query(models.VendorBid).filter(models.VendorBid.pr_id == pr.id).all()
    if not bids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No vendor bids exist for this purchase request."
        )

    # 1. Compute current scores for all bids to determine top 3
    scored_bids = []
    for bid in bids:
        vendor = bid.vendor
        performances = db.query(models.VendorPerformance).filter(
            models.VendorPerformance.vendor_id == vendor.id
        ).all()
        score_res = compute_vendor_score(
            vendor=vendor,
            quoted_price=bid.quoted_price,
            bid_days=bid.delivery_days,
            budget=pr.estimated_budget,
            performances=performances
        )
        scored_bids.append({
            "bid": bid,
            "vendor": vendor,
            "score": score_res["scores"]["total_score"],
            "score_res": score_res
        })

    # Sort descending by composite score
    scored_bids.sort(key=lambda x: x["score"], reverse=True)
    top_3_entries = scored_bids[:3]

    # 2. Prepare payload for LangGraph multi-agent execution
    pr_payload = {
        "id": pr.id,
        "title": pr.title,
        "item_description": pr.item_description,
        "quantity": pr.quantity,
        "estimated_budget": pr.estimated_budget,
        "urgency": pr.urgency,
        "department": pr.department
    }

    top_vendors_payload = [
        {
            "vendor_id": entry["vendor"].id,
            "vendor_name": entry["vendor"].name,
            "pricing_tier": entry["vendor"].pricing_tier,
            "quoted_price": entry["bid"].quoted_price,
            "delivery_days": entry["bid"].delivery_days,
            "avg_delivery_days": entry["vendor"].avg_delivery_days
        }
        for entry in top_3_entries
    ]

    # 3. Execute LangGraph StateGraph
    negotiation_state = run_multi_agent_negotiation(pr_payload, top_vendors_payload)

    # 4. Update database records with negotiated values and transcripts
    results: List[schemas.VendorNegotiationResultOut] = []
    total_initial = 0.0
    total_negotiated = 0.0

    for vs in negotiation_state["vendors"]:
        v_id = vs["vendor_id"]
        # Locate matching bid
        matching_entry = next((e for e in top_3_entries if e["vendor"].id == v_id), None)
        if matching_entry:
            bid = matching_entry["bid"]
            vendor = matching_entry["vendor"]

            orig_price = bid.original_quoted_price if bid.original_quoted_price is not None else vs["initial_price"]
            orig_days = bid.original_delivery_days if bid.original_delivery_days is not None else vs["initial_days"]

            bid.original_quoted_price = orig_price
            bid.original_delivery_days = orig_days
            bid.quoted_price = vs["final_price"]
            bid.delivery_days = vs["final_days"]
            bid.negotiation_transcript = json.dumps(vs["transcript"])

            # Compute new vendor score
            performances = db.query(models.VendorPerformance).filter(
                models.VendorPerformance.vendor_id == vendor.id
            ).all()
            new_score_res = compute_vendor_score(
                vendor=vendor,
                quoted_price=bid.quoted_price,
                bid_days=bid.delivery_days,
                budget=pr.estimated_budget,
                performances=performances
            )
            bid.bid_score = new_score_res["scores"]["total_score"]

            savings = max(0.0, orig_price - vs["final_price"])
            savings_pct = round((savings / orig_price) * 100.0, 2) if orig_price > 0 else 0.0
            days_saved = max(0, orig_days - vs["final_days"])

            total_initial += orig_price
            total_negotiated += vs["final_price"]

            turns = [
                schemas.NegotiationTurnOut(
                    round=t["round"],
                    speaker=t["speaker"],
                    speaker_role=t["speaker_role"],
                    message=t["message"],
                    offered_price=t["offered_price"],
                    offered_days=t["offered_days"],
                    is_fallback=t.get("is_fallback", False)
                )
                for t in vs["transcript"]
            ]

            results.append(schemas.VendorNegotiationResultOut(
                vendor_id=vendor.id,
                vendor_name=vendor.name,
                pricing_tier=vendor.pricing_tier,
                original_price=round(orig_price, 2),
                negotiated_price=round(vs["final_price"], 2),
                original_days=int(orig_days),
                negotiated_days=int(vs["final_days"]),
                savings_amount=round(savings, 2),
                savings_pct=savings_pct,
                days_saved=days_saved,
                status=vs.get("status", "completed"),
                transcript=turns,
                updated_score=new_score_res["scores"]["total_score"]
            ))

    db.commit()

    # 5. Build full refreshed recommendations list
    all_bids = db.query(models.VendorBid).filter(models.VendorBid.pr_id == pr.id).all()
    refreshed_recs: List[schemas.VendorRecommendation] = []
    for bid in all_bids:
        vendor = bid.vendor
        performances = db.query(models.VendorPerformance).filter(
            models.VendorPerformance.vendor_id == vendor.id
        ).all()
        score_res = compute_vendor_score(
            vendor=vendor,
            quoted_price=bid.quoted_price,
            bid_days=bid.delivery_days,
            budget=pr.estimated_budget,
            performances=performances
        )
        bid.bid_score = score_res["scores"]["total_score"]

        transcript_list = None
        if bid.negotiation_transcript:
            try:
                transcript_list = json.loads(bid.negotiation_transcript)
            except Exception:
                transcript_list = None

        rec = schemas.VendorRecommendation(
            bid_id=bid.id,
            vendor_id=vendor.id,
            vendor_name=vendor.name,
            pricing_tier=vendor.pricing_tier,
            contact_email=vendor.contact_email,
            quoted_price=bid.quoted_price,
            original_quoted_price=bid.original_quoted_price,
            estimated_budget=pr.estimated_budget,
            delivery_days=bid.delivery_days,
            original_delivery_days=bid.original_delivery_days,
            avg_delivery_days=vendor.avg_delivery_days,
            reliability_score=vendor.reliability_score,
            history_score_raw=score_res["history_score_raw"],
            notes=bid.notes,
            scores=schemas.ScoreBreakdown(**score_res["scores"]),
            rank=0,
            is_local_vendor=bool(getattr(vendor, "is_local_vendor", False)),
            is_incubator=bool(getattr(vendor, "is_incubator", False)),
            local_proximity_km=getattr(vendor, "local_proximity_km", 15.0),
            negotiation_transcript=transcript_list
        )
        refreshed_recs.append(rec)

    db.commit()

    # Rank by total score descending
    refreshed_recs.sort(key=lambda x: x.scores.total_score, reverse=True)
    for idx, rec in enumerate(refreshed_recs, start=1):
        rec.rank = idx

    total_savings = max(0.0, total_initial - total_negotiated)
    total_savings_pct = round((total_savings / total_initial) * 100.0, 2) if total_initial > 0 else 0.0

    top_winner = refreshed_recs[0] if refreshed_recs else None

    return schemas.NegotiationResponse(
        pr_id=pr.id,
        pr_title=pr.title,
        estimated_budget=pr.estimated_budget,
        total_initial_spend=round(total_initial, 2),
        total_negotiated_spend=round(total_negotiated, 2),
        total_savings=round(total_savings, 2),
        total_savings_pct=total_savings_pct,
        top_vendor_id=top_winner.vendor_id if top_winner else 0,
        top_vendor_name=top_winner.vendor_name if top_winner else "",
        results=results,
        recommendations=refreshed_recs
    )
