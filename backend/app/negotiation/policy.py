"""
policy.py - Deterministic policy evaluation engine.
Enforces authority boundaries, ceilings, floors, and escalation rules without LLM intervention.
"""
from typing import Any, Dict, Literal, TypedDict
from app.negotiation.state import GraphNegotiationState, SingleVendorState

MAX_ROUNDS: int = 3
PRICE_FLOOR_PCT: float = 0.85


class PolicyEvaluationResult(TypedDict):
    action: Literal["CONTINUE", "ACCEPT", "REJECT", "ESCALATE"]
    status: str
    policy_reason: str
    rule_triggered: str
    threshold_value: str | None
    actual_value: str | None
    final_price: float | None
    final_days: int | None


def evaluate_vendor_policy(
    current_price: float,
    current_days: int,
    estimated_budget: float,
    price_floor: float,
    delivery_floor: int,
    current_round: int,
    max_rounds: int = MAX_ROUNDS,
) -> PolicyEvaluationResult:
    """
    Pure deterministic policy check for an individual vendor quotation.
    Categorizes the terms into CONTINUE, ACCEPT, REJECT, or ESCALATE.
    """
    # 1. Breach of vendor minimum viable price floor
    if current_price < price_floor:
        return {
            "action": "ESCALATE",
            "status": "ESCALATED",
            "policy_reason": "Requested price crossed the authorized lower boundary.",
            "rule_triggered": "PRICE_FLOOR_VIOLATION",
            "threshold_value": f"${price_floor:,.2f}",
            "actual_value": f"${current_price:,.2f}",
            "final_price": None,
            "final_days": None,
        }

    # 2. Breach of delivery feasibility floor
    if current_days < delivery_floor:
        return {
            "action": "ESCALATE",
            "status": "ESCALATED",
            "policy_reason": "Requested delivery crosses the authorized delivery boundary.",
            "rule_triggered": "DELIVERY_FLOOR_VIOLATION",
            "threshold_value": f"{delivery_floor} days",
            "actual_value": f"{current_days} days",
            "final_price": None,
            "final_days": None,
        }

    # 3. Extreme budget overrun (> 150% of budget) - non-negotiable rejection
    if current_price > (estimated_budget * 1.5):
        return {
            "action": "REJECT",
            "status": "REJECTED",
            "policy_reason": "Quotation severely exceeds budgetary parameters beyond negotiable range.",
            "rule_triggered": "EXCESSIVE_BUDGET_OVERRUN",
            "threshold_value": f"${estimated_budget * 1.5:,.2f}",
            "actual_value": f"${current_price:,.2f}",
            "final_price": None,
            "final_days": None,
        }

    # 4. Budget ceiling exceeded
    if current_price > estimated_budget:
        return {
            "action": "ESCALATE",
            "status": "ESCALATED",
            "policy_reason": "Negotiated price exceeds the procurement budget ceiling.",
            "rule_triggered": "BUDGET_CEILING_EXCEEDED",
            "threshold_value": f"${estimated_budget:,.2f}",
            "actual_value": f"${current_price:,.2f}",
            "final_price": None,
            "final_days": None,
        }

    # 5. Terms comply with budget and consensus reached (round >= 2 or final round)
    if current_price <= estimated_budget and current_round >= 2:
        return {
            "action": "ACCEPT",
            "status": "COMPLETED",
            "policy_reason": "Terms satisfy the configured procurement policy.",
            "rule_triggered": "POLICY_SATISFIED",
            "threshold_value": f"<=${estimated_budget:,.2f}",
            "actual_value": f"${current_price:,.2f}",
            "final_price": current_price,
            "final_days": current_days,
        }

    # 6. Maximum negotiation rounds exhausted without agreement
    if current_round >= max_rounds:
        return {
            "action": "ESCALATE",
            "status": "ESCALATED",
            "policy_reason": "Maximum negotiation rounds reached without an authorized agreement.",
            "rule_triggered": "MAX_ROUNDS_REACHED",
            "threshold_value": f"Max {max_rounds} rounds",
            "actual_value": f"Round {current_round}",
            "final_price": None,
            "final_days": None,
        }

    # 7. Within policy boundaries, can continue negotiating
    return {
        "action": "CONTINUE",
        "status": "NEGOTIATING",
        "policy_reason": "Terms remain within policy and negotiation can continue.",
        "rule_triggered": "WITHIN_POLICY_CONTINUE",
        "threshold_value": f"Round {current_round} < {max_rounds}",
        "actual_value": f"${current_price:,.2f}",
        "final_price": None,
        "final_days": None,
    }


def node_policy_evaluation(state: GraphNegotiationState) -> GraphNegotiationState:
    """
    LangGraph node: deterministically evaluates every active vendor in the state.
    """
    budget = float(state["estimated_budget"])
    round_number = int(state["current_round"])

    for vendor in state["vendors"]:
        if vendor["action"] != "CONTINUE":
            continue

        result = evaluate_vendor_policy(
            current_price=vendor["current_price"],
            current_days=vendor["current_days"],
            estimated_budget=budget,
            price_floor=vendor["price_floor"],
            delivery_floor=vendor["delivery_floor"],
            current_round=round_number,
            max_rounds=MAX_ROUNDS,
        )

        vendor["action"] = result["action"]
        vendor["status"] = result["status"]
        vendor["policy_reason"] = result["policy_reason"]

        if result["action"] == "ACCEPT":
            vendor["final_price"] = result["final_price"]
            vendor["final_days"] = result["final_days"]

    return state


def route_policy(state: GraphNegotiationState) -> str:
    """
    Conditional routing function for LangGraph:
    Loops back to buyer_turn if any vendor has CONTINUE.
    Otherwise ends the graph.
    """
    if any(v["action"] == "CONTINUE" for v in state["vendors"]):
        return "buyer_turn"

    return "end"
