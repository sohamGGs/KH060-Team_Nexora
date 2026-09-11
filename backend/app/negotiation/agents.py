import os
import json
import logging
import concurrent.futures
from typing import TypedDict, List, Dict, Any, Optional, Literal
from langgraph.graph import StateGraph, END

logger = logging.getLogger("procureiq.negotiation")


def call_gemini_with_timeout(prompt: str, timeout_seconds: float = 5.0) -> Optional[str]:
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key or "your_gemini_api_key" in api_key.lower():
        return None

    def _worker():
        from google import genai
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=genai.types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.3,
                max_output_tokens=200
            )
        )
        return response.text

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(_worker)
        try:
            return future.result(timeout=timeout_seconds)
        except Exception as e:
            logger.warning(f"Gemini negotiation LLM call failed or timed out ({timeout_seconds}s): {e}")
            return None


class NegotiationTurn(TypedDict):
    round: int
    speaker: str
    speaker_role: str
    message: str
    offered_price: float
    offered_days: int
    is_fallback: bool


class SingleVendorState(TypedDict):
    vendor_id: int
    vendor_name: str
    pricing_tier: str
    initial_price: float
    initial_days: int
    avg_delivery_days: int
    price_floor: float
    delivery_floor: int
    current_price: float
    current_days: int
    transcript: List[Dict[str, Any]]
    final_price: float
    final_days: int
    is_fallback: bool
    status: str
    action: Literal["CONTINUE", "ACCEPT", "REJECT", "ESCALATE"]


class GraphNegotiationState(TypedDict):
    pr_id: int
    pr_title: str
    item_description: str
    quantity: int
    estimated_budget: float
    urgency: str
    department: str
    vendors: List[SingleVendorState]
    current_round: int


def node_buyer_turn(state: GraphNegotiationState) -> GraphNegotiationState:
    updated_vendors = []
    # Increment round at the start of buyer turn
    current_round = state.get("current_round", 0) + 1
    
    for v in state["vendors"]:
        if v.get("action", "CONTINUE") != "CONTINUE":
            updated_vendors.append(v)
            continue

        initial_price = v["initial_price"]
        initial_days = v["initial_days"]
        budget = state["estimated_budget"]

        if current_round == 1:
            prompt = f"""
You are the Chief Procurement Buyer Agent for NetSuite ERP.
Generate an opening counter-offer (Round 1) for vendor "{v['vendor_name']}" ({v['pricing_tier']}).
PR Title: {state['pr_title']}
Budget: ${budget}
Vendor Initial Quote: ${initial_price} with {initial_days} days SLA.

Goal: Politely but firmly negotiate a lower price (~10-15% below quote) and faster delivery.
Return raw JSON:
{{
  "message": "<1-2 sentence professional procurement opening offer>",
  "offered_price": <target price number>,
  "offered_days": <target days integer>
}}
"""
        else:
            # Counter-offer
            vendor_last = v["transcript"][-1]
            prompt = f"""
You are the Chief Procurement Buyer Agent for NetSuite ERP.
Negotiation Round {current_round} with vendor "{v['vendor_name']}".
Vendor just offered: ${vendor_last['offered_price']} and {vendor_last['offered_days']} days.
Budget: ${budget}

Make a counter-offer. 
Goal: Negotiate a lower price and faster delivery.
Return raw JSON:
{{
  "message": "<1-2 sentence counter offer or closing statement>",
  "offered_price": <target price number>,
  "offered_days": <target days integer>
}}
"""

        llm_raw = call_gemini_with_timeout(prompt, timeout_seconds=5.0)
        parsed = None
        if llm_raw:
            try:
                parsed = json.loads(llm_raw)
            except Exception:
                pass

        if parsed and "offered_price" in parsed and "message" in parsed:
            target_price = round(float(parsed["offered_price"]), 2)
            target_price = max(v["price_floor"], min(initial_price * 0.95, target_price))
            target_days = max(v["delivery_floor"], int(parsed.get("offered_days", initial_days - 1)))
            message = str(parsed["message"])
            is_fb = False
        else:
            # Fallback buyer offer
            if current_round == 1:
                target_price = round(initial_price * 0.88, 2)
                target_days = max(v["delivery_floor"], initial_days - 1)
                message = f"We are reviewing quotations for {state['pr_title']}. We can execute an immediate award if you can adjust pricing to ${target_price:,.2f} with a {target_days}-day delivery window."
            else:
                target_price = v["current_price"]
                target_days = v["current_days"]
                message = f"Please consider our previous offer of ${target_price:,.2f}."
            is_fb = True

        turn = {
            "round": current_round,
            "speaker": "BuyerAgent (ProcureIQ AI)",
            "speaker_role": "buyer",
            "message": message,
            "offered_price": target_price,
            "offered_days": target_days,
            "is_fallback": is_fb
        }
        v["current_price"] = target_price
        v["current_days"] = target_days
        v["transcript"].append(turn)
        updated_vendors.append(v)

    return {**state, "vendors": updated_vendors, "current_round": current_round}


def node_vendor_turn(state: GraphNegotiationState) -> GraphNegotiationState:
    updated_vendors = []
    current_round = state["current_round"]
    
    for v in state["vendors"]:
        if v.get("action", "CONTINUE") != "CONTINUE":
            updated_vendors.append(v)
            continue

        tier = v["pricing_tier"]
        initial_price = v["initial_price"]
        initial_days = v["initial_days"]
        price_floor = v["price_floor"]
        delivery_floor = v["delivery_floor"]
        
        buyer_turn = v["transcript"][-1]
        buyer_price = buyer_turn["offered_price"]
        buyer_days = buyer_turn["offered_days"]

        tier_persona = ""
        if tier == "Enterprise Tier-1":
            tier_persona = "Enterprise Tier-1: Firm on price (minimal discount 3-6%), highlighting ISO quality, premium warranty and SLA reliability. Flexible on expediting delivery."
        elif tier == "Economy Tier":
            tier_persona = "Economy Tier: Highly price-flexible (can offer 10-14% discount towards price floor), but strict on delivery scheduling (cannot expedite easily)."
        else:
            tier_persona = "Mid-Tier: Balanced approach, offering a 7-10% discount in exchange for fast PO confirmation."

        prompt = f"""
You are the automated Vendor Sales Agent for "{v['vendor_name']}".
Tier: {tier} ({tier_persona})
Your Initial Quote: ${initial_price}, {initial_days} days.
Your Secret Price Floor: ${price_floor} (DO NOT GO BELOW THIS)
Your Delivery Floor: {delivery_floor} days.

Buyer just offered: ${buyer_price} and {buyer_days} days.
Generate your Round {current_round} Counter-Offer. Return raw JSON:
{{
  "message": "<1-2 sentence professional vendor response with one line of reasoning>",
  "counter_price": <counter price number >= {price_floor}>,
  "counter_days": <counter delivery days integer >= {delivery_floor}>
}}
"""
        llm_raw = call_gemini_with_timeout(prompt, timeout_seconds=5.0)
        parsed = None
        if llm_raw:
            try:
                parsed = json.loads(llm_raw)
            except Exception:
                pass

        if parsed and "counter_price" in parsed and "message" in parsed:
            counter_p = max(price_floor, float(parsed["counter_price"]))
            counter_d = max(delivery_floor, int(parsed.get("counter_days", initial_days)))
            msg = str(parsed["message"])
            is_fb = False
        else:
            # Fallback vendor response
            if tier == "Enterprise Tier-1":
                counter_p = round(initial_price * 0.95, 2)
                counter_d = max(delivery_floor, initial_days - 1)
                msg = f"Given our Tier-1 ISO quality assurance and full 2-year warranty, our best concession is ${counter_p:,.2f} with {counter_d}-day expedited delivery."
            elif tier == "Economy Tier":
                counter_p = round(initial_price * 0.88, 2)
                counter_d = initial_days
                msg = f"We can aggressively discount to ${counter_p:,.2f} to win this order, though our standard {counter_d}-day logistics window remains fixed."
            else:
                counter_p = round(initial_price * 0.92, 2)
                counter_d = max(delivery_floor, initial_days - 1)
                msg = f"In appreciation of a direct award, we can meet at ${counter_p:,.2f} and commit to delivery within {counter_d} business days."
            is_fb = True

        turn = {
            "round": current_round,
            "speaker": f"VendorAgent: {v['vendor_name']}",
            "speaker_role": "vendor",
            "message": msg,
            "offered_price": round(counter_p, 2),
            "offered_days": int(counter_d),
            "is_fallback": is_fb
        }
        v["current_price"] = round(counter_p, 2)
        v["current_days"] = int(counter_d)
        v["transcript"].append(turn)
        updated_vendors.append(v)

    return {**state, "vendors": updated_vendors}


def node_policy_evaluation(state: GraphNegotiationState) -> GraphNegotiationState:
    updated_vendors = []
    current_round = state["current_round"]
    budget = state["estimated_budget"]
    MAX_ROUNDS = 3
    
    for v in state["vendors"]:
        if v.get("action", "CONTINUE") != "CONTINUE":
            updated_vendors.append(v)
            continue
            
        price = v["current_price"]
        days = v["current_days"]
        
        # Policy rules
        if price <= budget and price >= v["price_floor"]: 
            v["action"] = "ACCEPT"
            v["status"] = "completed"
            v["final_price"] = price
            v["final_days"] = days
            # Append closing transcript
            v["transcript"].append({
                "round": current_round,
                "speaker": "System Policy",
                "speaker_role": "system",
                "message": f"Agreement reached. Terms align with budget (${budget:,.2f}).",
                "offered_price": price,
                "offered_days": days,
                "is_fallback": False
            })
        elif current_round >= MAX_ROUNDS:
            # Reached max rounds
            if price <= v["initial_price"]:
                v["action"] = "ACCEPT"
                v["status"] = "completed"
                v["final_price"] = price
                v["final_days"] = days
                v["transcript"].append({
                    "round": current_round,
                    "speaker": "System Policy",
                    "speaker_role": "system",
                    "message": "Max negotiation rounds reached. Locking final best offer.",
                    "offered_price": price,
                    "offered_days": days,
                    "is_fallback": False
                })
            else:
                v["action"] = "ESCALATE"
                v["status"] = "escalated"
                v["final_price"] = v["initial_price"]
                v["final_days"] = v["initial_days"]
                v["transcript"].append({
                    "round": current_round,
                    "speaker": "System Policy",
                    "speaker_role": "system",
                    "message": "Negotiation stalled without discount. Escalating for manual review.",
                    "offered_price": v["initial_price"],
                    "offered_days": v["initial_days"],
                    "is_fallback": False
                })
        else:
            v["action"] = "CONTINUE"
            v["status"] = "negotiating"
            
        updated_vendors.append(v)
        
    return {**state, "vendors": updated_vendors}


def node_escalation(state: GraphNegotiationState) -> GraphNegotiationState:
    # A placeholder node for Phase 1. Further logic can be injected here later.
    return state


def route_policy(state: GraphNegotiationState) -> str:
    actions = [v.get("action", "CONTINUE") for v in state["vendors"]]
    if "CONTINUE" in actions:
        return "buyer_turn"
    elif "ESCALATE" in actions:
        return "escalation"
    else:
        return END


# Build LangGraph StateGraph
def create_negotiation_graph():
    builder = StateGraph(GraphNegotiationState)
    builder.add_node("buyer_turn", node_buyer_turn)
    builder.add_node("vendor_turn", node_vendor_turn)
    builder.add_node("policy_evaluation", node_policy_evaluation)
    builder.add_node("escalation", node_escalation)

    builder.set_entry_point("buyer_turn")
    builder.add_edge("buyer_turn", "vendor_turn")
    builder.add_edge("vendor_turn", "policy_evaluation")
    builder.add_conditional_edges("policy_evaluation", route_policy)
    builder.add_edge("escalation", END)

    return builder.compile()


compiled_graph = create_negotiation_graph()


def run_multi_agent_negotiation(
    pr_data: Dict[str, Any],
    top_vendors_data: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Executes a conditional stateful LangGraph negotiation across the top vendors.
    Guaranteed per-call 5s LLM timeout with resilient fallback.
    """
    vendor_states: List[SingleVendorState] = []
    for v in top_vendors_data:
        quoted_price = float(v["quoted_price"])
        delivery_days = int(v["delivery_days"])
        avg_days = int(v.get("avg_delivery_days", delivery_days))

        price_floor = round(quoted_price * 0.85, 2)
        delivery_floor = max(1, avg_days - 1)

        vendor_states.append({
            "vendor_id": v["vendor_id"],
            "vendor_name": v["vendor_name"],
            "pricing_tier": v.get("pricing_tier", "Mid-Tier"),
            "initial_price": quoted_price,
            "initial_days": delivery_days,
            "avg_delivery_days": avg_days,
            "price_floor": price_floor,
            "delivery_floor": delivery_floor,
            "current_price": quoted_price,
            "current_days": delivery_days,
            "transcript": [],
            "final_price": quoted_price,
            "final_days": delivery_days,
            "is_fallback": False,
            "status": "pending",
            "action": "CONTINUE"
        })

    initial_state: GraphNegotiationState = {
        "pr_id": pr_data.get("id", 0),
        "pr_title": pr_data.get("title", "Purchase Request"),
        "item_description": pr_data.get("item_description", ""),
        "quantity": pr_data.get("quantity", 1),
        "estimated_budget": float(pr_data.get("estimated_budget", 0.0)),
        "urgency": pr_data.get("urgency", "Standard"),
        "department": pr_data.get("department", "Operations"),
        "vendors": vendor_states,
        "current_round": 0
    }

    try:
        final_state = compiled_graph.invoke(initial_state)
        return final_state
    except Exception as e:
        logger.error(f"LangGraph execution error, applying fallback: {e}")
        # Ensure complete fallback return so endpoint NEVER returns 500
        fallback_vendors = []
        for vs in vendor_states:
            init_p = vs["initial_price"]
            init_d = vs["initial_days"]
            fallback_transcript = [
                {
                    "round": 1,
                    "speaker": "BuyerAgent (ProcureIQ AI)",
                    "speaker_role": "buyer",
                    "message": f"We are reviewing quotation terms for {initial_state['pr_title']}.",
                    "offered_price": init_p,
                    "offered_days": init_d,
                    "is_fallback": True
                },
                {
                    "round": 1,
                    "speaker": f"VendorAgent: {vs['vendor_name']}",
                    "speaker_role": "vendor",
                    "message": "Negotiation unavailable — original quote retained under standard procurement terms.",
                    "offered_price": init_p,
                    "offered_days": init_d,
                    "is_fallback": True
                },
                {
                    "round": 1,
                    "speaker": "System Policy",
                    "speaker_role": "system",
                    "message": "Original quote retained as binding benchmark.",
                    "offered_price": init_p,
                    "offered_days": init_d,
                    "is_fallback": True
                }
            ]
            vs["transcript"] = fallback_transcript
            vs["final_price"] = init_p
            vs["final_days"] = init_d
            vs["status"] = "completed"
            vs["action"] = "ACCEPT"
            vs["is_fallback"] = True
            fallback_vendors.append(vs)
        return {**initial_state, "vendors": fallback_vendors, "current_round": 1}

