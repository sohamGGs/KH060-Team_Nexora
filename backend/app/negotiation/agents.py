"""
agents.py - LLM agent behaviors (Buyer & Vendor) and compatibility wrappers.
Focuses strictly on agent reasoning and translation between LLM output and negotiation state.
"""
import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from typing import Any, Dict, List

from google import genai

from app.negotiation.prompts import build_buyer_prompt, build_vendor_prompt
from app.negotiation.state import (
    GraphNegotiationState,
    NegotiationTurn,
    SingleVendorState,
)
from app.negotiation.policy import (
    MAX_ROUNDS,
    PRICE_FLOOR_PCT,
    node_policy_evaluation,
    route_policy,
)

logger = logging.getLogger(__name__)


def call_gemini_with_timeout(prompt: str, timeout_seconds: float = 8.0) -> Dict[str, Any] | None:
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        return None

    def call() -> Dict[str, Any]:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config={
                "temperature": 0.2,
                "response_mime_type": "application/json",
                "max_output_tokens": 300,
            },
        )
        text = (response.text or "").strip()
        return json.loads(text)

    executor = ThreadPoolExecutor(max_workers=1)
    future = executor.submit(call)

    try:
        return future.result(timeout=timeout_seconds)
    except (TimeoutError, Exception) as exc:
        logger.warning("Gemini negotiation call failed: %s", exc)
        return None
    finally:
        executor.shutdown(wait=False, cancel_futures=True)


def _vendor_label(vendor: SingleVendorState) -> str:
    return f"{vendor['vendor_name']} ({vendor['pricing_tier']})"


def _build_vendor_state(
    vendor: Dict[str, Any],
    estimated_budget: float,
) -> SingleVendorState:
    initial_price = float(vendor.get("initial_price") or vendor.get("quoted_price", 0.0))
    initial_days = int(vendor.get("initial_days") or vendor.get("delivery_days", 1))
    avg_days = int(vendor.get("avg_delivery_days") or initial_days)

    return {
        "vendor_id": int(vendor["vendor_id"]),
        "vendor_name": vendor["vendor_name"],
        "pricing_tier": vendor.get("pricing_tier", "Mid-Tier"),
        "initial_price": initial_price,
        "initial_days": initial_days,
        "avg_delivery_days": avg_days,
        "estimated_budget": estimated_budget,
        "price_floor": round(initial_price * PRICE_FLOOR_PCT, 2),
        "delivery_floor": max(1, avg_days - 1),
        "current_price": initial_price,
        "current_days": initial_days,
        "transcript": [],
        "final_price": initial_price,
        "final_days": initial_days,
        "is_fallback": False,
        "status": "INITIATED",
        "action": "CONTINUE",
        "policy_reason": "",
    }


def node_buyer_turn(state: GraphNegotiationState) -> GraphNegotiationState:
    """
    Agent node: Formulates Buyer's counter-proposals to active vendors.
    """
    round_number = state["current_round"] + 1
    state["current_round"] = round_number

    for vendor in state["vendors"]:
        if vendor["action"] != "CONTINUE":
            continue

        previous_vendor_price = vendor["current_price"]
        previous_vendor_days = vendor["current_days"]

        prompt = build_buyer_prompt(
            item_description=state["item_description"],
            quantity=state["quantity"],
            estimated_budget=state["estimated_budget"],
            urgency=state["urgency"],
            vendor_name=vendor["vendor_name"],
            pricing_tier=vendor["pricing_tier"],
            current_price=previous_vendor_price,
            current_days=previous_vendor_days,
            price_floor=vendor["price_floor"],
            delivery_floor=vendor["delivery_floor"],
            round_number=round_number,
        )

        result = call_gemini_with_timeout(prompt)

        if result:
            target_price = float(result.get("target_price", previous_vendor_price))
            target_days = int(result.get("target_delivery_days", previous_vendor_days))
            message = str(result.get("message", "Please provide your best revised quotation."))
        else:
            target_price = previous_vendor_price * (0.88 if round_number == 1 else 0.95)
            target_days = max(vendor["delivery_floor"], previous_vendor_days - 1)
            message = (
                "Please provide your best revised quotation within our approved "
                "procurement requirements."
            )
            vendor["is_fallback"] = True

        # Clamp within authorized boundaries
        target_price = max(vendor["price_floor"], target_price)
        target_price = min(state["estimated_budget"], target_price)
        target_days = max(vendor["delivery_floor"], target_days)

        vendor["current_price"] = round(target_price, 2)
        vendor["current_days"] = target_days

        vendor["transcript"].append(
            {
                "round": round_number,
                "speaker": "BuyerAgent",
                "speaker_role": "BUYER",
                "message": message,
                "offered_price": vendor["current_price"],
                "offered_days": vendor["current_days"],
                "is_fallback": vendor["is_fallback"],
            }
        )

    return state


def node_vendor_turn(state: GraphNegotiationState) -> GraphNegotiationState:
    """
    Agent node: Simulates Vendor's counter-proposal based on tier persona.
    """
    round_number = state["current_round"]

    for vendor in state["vendors"]:
        if vendor["action"] != "CONTINUE":
            continue

        buyer_price = vendor["current_price"]
        buyer_days = vendor["current_days"]

        prompt = build_vendor_prompt(
            vendor_name=vendor["vendor_name"],
            pricing_tier=vendor["pricing_tier"],
            buyer_price=buyer_price,
            buyer_days=buyer_days,
            initial_price=vendor["initial_price"],
            initial_days=vendor["initial_days"],
            price_floor=vendor["price_floor"],
            delivery_floor=vendor["delivery_floor"],
        )

        result = call_gemini_with_timeout(prompt)

        if result:
            counter_price = float(result.get("counter_price", buyer_price))
            counter_days = int(result.get("counter_delivery_days", buyer_days))
            message = str(result.get("message", "We can revise our quotation."))
        else:
            if round_number == 1:
                concession = 0.05
            elif round_number == 2:
                concession = 0.03
            else:
                concession = 0.01

            counter_price = max(vendor["price_floor"], vendor["current_price"] * (1 - concession))
            counter_days = max(vendor["delivery_floor"], vendor["current_days"])
            message = (
                f"We can offer a revised rate of ${counter_price:,.2f} with {counter_days}-day delivery."
            )
            vendor["is_fallback"] = True

        # Clamp within vendor viability boundaries
        counter_price = max(vendor["price_floor"], counter_price)
        counter_price = min(vendor["initial_price"], counter_price)
        counter_days = max(vendor["delivery_floor"], counter_days)

        vendor["current_price"] = round(counter_price, 2)
        vendor["current_days"] = counter_days

        vendor["transcript"].append(
            {
                "round": round_number,
                "speaker": vendor["vendor_name"],
                "speaker_role": "VENDOR",
                "message": message,
                "offered_price": vendor["current_price"],
                "offered_days": vendor["current_days"],
                "is_fallback": vendor["is_fallback"],
            }
        )

    return state


# =====================================================================
# Compatibility Wrappers
# Callers importing run_multi_agent_negotiation / resume_negotiation
# from app.negotiation.agents continue working without breakage.
# =====================================================================

def run_multi_agent_negotiation(*args, **kwargs):
    from app.negotiation.graph import run_negotiation
    return run_negotiation(*args, **kwargs)


def resume_negotiation(*args, **kwargs):
    from app.negotiation.graph import resume_negotiation_graph
    return resume_negotiation_graph(*args, **kwargs)
