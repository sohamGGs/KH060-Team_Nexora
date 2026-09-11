"""
graph.py - LangGraph assembly, conditional routing, and graph execution.
Orchestrates buyer -> vendor -> policy evaluation loop.
Fails safely into ESCALATE rather than ACCEPT.
"""
import logging
from typing import Any, Dict, List

from langgraph.graph import END, StateGraph

from app.negotiation.agents import (
    _build_vendor_state,
    node_buyer_turn,
    node_vendor_turn,
)
from app.negotiation.policy import node_policy_evaluation, route_policy
from app.negotiation.state import (
    GraphNegotiationState,
    NegotiationTurn,
    SingleVendorState,
)

logger = logging.getLogger(__name__)


def build_negotiation_graph() -> StateGraph:
    """
    Constructs the LangGraph state machine with deterministic conditional routing.
    """
    graph = StateGraph(GraphNegotiationState)

    graph.add_node("buyer_turn", node_buyer_turn)
    graph.add_node("vendor_turn", node_vendor_turn)
    graph.add_node("policy_evaluation", node_policy_evaluation)

    graph.set_entry_point("buyer_turn")
    graph.add_edge("buyer_turn", "vendor_turn")
    graph.add_edge("vendor_turn", "policy_evaluation")

    graph.add_conditional_edges(
        "policy_evaluation",
        route_policy,
        {
            "buyer_turn": "buyer_turn",
            "end": END,
        },
    )

    return graph


def run_negotiation(
    pr_id: int | Dict[str, Any] = 0,
    pr_title: str | None = None,
    item_description: str = "",
    quantity: int = 1,
    estimated_budget: float = 0.0,
    urgency: str = "Medium",
    department: str = "Operations",
    vendors: List[Dict[str, Any]] | None = None,
    *args,
    **kwargs,
) -> GraphNegotiationState:
    """
    Executes the multi-agent negotiation graph for a purchase request.
    Supports both keyword args and positional dict args for testing compatibility.
    """
    # Handle dict signature: run_multi_agent_negotiation(dummy_pr, dummy_vendors)
    if isinstance(pr_id, dict):
        pr_dict = pr_id
        vendor_list = pr_title if isinstance(pr_title, list) else (args[0] if args else (vendors or []))
        target_pr_id = int(pr_dict.get("id", 0))
        target_pr_title = str(pr_dict.get("title", ""))
        target_item_desc = str(pr_dict.get("item_description", ""))
        target_quantity = int(pr_dict.get("quantity", 1))
        target_budget = float(pr_dict.get("estimated_budget", 0.0))
        target_urgency = str(pr_dict.get("urgency", "Medium"))
        target_dept = str(pr_dict.get("department", "Operations"))
    else:
        target_pr_id = int(pr_id)
        target_pr_title = str(pr_title or kwargs.get("title", ""))
        target_item_desc = str(item_description or kwargs.get("description", ""))
        target_quantity = int(quantity)
        target_budget = float(estimated_budget)
        target_urgency = str(urgency)
        target_dept = str(department)
        vendor_list = vendors or kwargs.get("vendor_list", [])

    vendor_states: List[SingleVendorState] = [
        _build_vendor_state(v, target_budget)
        for v in vendor_list
    ]

    initial_state: GraphNegotiationState = {
        "pr_id": target_pr_id,
        "pr_title": target_pr_title,
        "item_description": target_item_desc,
        "quantity": target_quantity,
        "estimated_budget": target_budget,
        "urgency": target_urgency,
        "department": target_dept,
        "vendors": vendor_states,
        "current_round": 0,
    }

    graph = build_negotiation_graph()
    compiled = graph.compile()

    try:
        return compiled.invoke(initial_state)
    except Exception as exc:
        logger.exception("Negotiation graph execution failed: %s", exc)

        # Fail safely into ESCALATE rather than ACCEPT
        for vendor in vendor_states:
            vendor["action"] = "ESCALATE"
            vendor["status"] = "ESCALATED"
            vendor["policy_reason"] = "Negotiation engine failed safely and requires human review."
            vendor["is_fallback"] = True

            vendor["transcript"].append(
                {
                    "round": 0,
                    "speaker": "System",
                    "speaker_role": "SYSTEM",
                    "message": "Negotiation paused for human review because the agent execution failed.",
                    "offered_price": vendor["current_price"],
                    "offered_days": vendor["current_days"],
                    "is_fallback": True,
                }
            )

        return initial_state


def resume_negotiation_graph(
    session: Dict[str, Any],
    vendor: Dict[str, Any],
    pr: Dict[str, Any],
    transcript: List[NegotiationTurn],
) -> Dict[str, Any]:
    """
    Resumes a paused negotiation session following human approval.
    """
    state = _build_vendor_state(
        {
            "vendor_id": vendor["id"],
            "vendor_name": vendor["name"],
            "pricing_tier": vendor.get("pricing_tier", "Mid-Tier"),
            "initial_price": session["current_price"],
            "initial_days": session["current_delivery_days"],
            "avg_delivery_days": vendor.get("avg_delivery_days", session["current_delivery_days"]),
        },
        float(pr["estimated_budget"]),
    )

    state["current_price"] = float(session["current_price"])
    state["current_days"] = int(session["current_delivery_days"])
    state["transcript"] = transcript
    state["final_price"] = state["current_price"]
    state["final_days"] = state["current_days"]
    state["action"] = "CONTINUE"
    state["status"] = "RESUMED"

    graph_state: GraphNegotiationState = {
        "pr_id": int(pr["id"]),
        "pr_title": pr["title"],
        "item_description": pr["item_description"],
        "quantity": int(pr["quantity"]),
        "estimated_budget": float(pr["estimated_budget"]),
        "urgency": pr["urgency"],
        "department": pr["department"],
        "vendors": [state],
        "current_round": int(session["current_round"]),
    }

    graph = build_negotiation_graph()
    compiled = graph.compile()

    try:
        return compiled.invoke(graph_state)
    except Exception as exc:
        logger.exception("Resume negotiation execution failed: %s", exc)
        state["action"] = "ESCALATE"
        state["status"] = "ESCALATED"
        state["policy_reason"] = "Resume execution failed safely and requires review."
        state["is_fallback"] = True
        return graph_state
