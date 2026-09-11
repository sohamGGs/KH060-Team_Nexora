import os
import json
import logging
from dotenv import load_dotenv
from google import genai
from google.genai import types

from app.negotiation.state import GraphNegotiationState
from app.negotiation.prompts import get_gov_system_prompt
from app.negotiation.policy import check_gov_policy

load_dotenv()
logger = logging.getLogger("negotiation.gov_agent")


def run_gov_agent(state: GraphNegotiationState) -> GraphNegotiationState:
    """
    Government Buyer AI Agent.
    Evaluates proposals and negotiates on behalf of the procurement officer.
    Employs Gemini LLM with safe deterministic fallback on API issues.
    """
    shared = state["shared"]
    gov = state["gov"]
    current_round = shared["current_round"]

    if current_round >= 3:
        state["next_actor"] = "END"
        if shared.get("status") not in ["ACCEPTED", "ESCALATED", "REJECTED"]:
            shared["status"] = "NEGOTIATING"
        return state

    # Locate last vendor proposal if any
    last_vendor_event = None
    for ev in reversed(shared["events"]):
        if ev.get("speaker_role") == "VENDOR_AGENT":
            last_vendor_event = ev
            break

    result = None
    api_key = os.getenv("GEMINI_API_KEY")

    if api_key:
        try:
            client = genai.Client(api_key=api_key)
            prompt = get_gov_system_prompt(shared, gov)
            response = client.models.generate_content(
                model="models/gemini-3.6-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.3,
                ),
            )
            if response and response.text:
                result = json.loads(response.text)
        except Exception as exc:
            logger.warning(f"Government agent Gemini call failed, using deterministic fallback: {exc}")
            result = None

    # Deterministic fallback logic if LLM failed or returned invalid response
    if not result or not isinstance(result, dict):
        if last_vendor_event is None:
            # Round 0 opening offer
            offered_price = round((gov["target_price"] * 2 + gov["max_authorized_price"]) / 3.0, 2)
            offered_days = int(gov["target_delivery"])
            event_type = "OFFER"
            message = f"Requesting initial commercial quotation at ${offered_price:,.2f} with {offered_days}-day SLA."
        else:
            v_price = float(last_vendor_event.get("price") or gov["max_authorized_price"])
            v_days = int(last_vendor_event.get("delivery_days") or gov["max_delivery"])

            if v_price <= gov["target_price"] * 1.05 and v_days <= gov["max_delivery"]:
                event_type = "ACCEPT"
                offered_price = v_price
                offered_days = v_days
                message = f"Agreement reached: Accepting vendor offer of ${v_price:,.2f} ({v_days} days)."
            elif v_price <= gov["max_authorized_price"]:
                event_type = "OFFER"
                offered_price = round(max(gov["target_price"], v_price * 0.95), 2)
                offered_days = min(v_days, gov["max_delivery"])
                message = f"Counter-offering ${offered_price:,.2f} with {offered_days} delivery days to meet department budget."
            else:
                event_type = "ESCALATE"
                offered_price = v_price
                offered_days = v_days
                message = f"Price ${v_price:,.2f} exceeds maximum authorized spend (${gov['max_authorized_price']:,.2f}). Escalating to procurement lead."

        result = {
            "event_type": event_type,
            "price": offered_price,
            "delivery_days": offered_days,
            "message": message,
        }

    event_type = result.get("event_type", "OFFER")
    price = result.get("price")
    days = result.get("delivery_days")
    message = result.get("message", "")

    if price is not None:
        price = float(price)
    if days is not None:
        days = int(days)

    # Enforce deterministic policy boundary check
    if event_type in ["OFFER", "ACCEPT"] and price is not None and days is not None:
        policy_res = check_gov_policy(price, days, gov)
        if not policy_res.is_authorized:
            event_type = "ESCALATE"
            message = f"Internal Policy Exception: {policy_res.reason}"

    shared["events"].append({
        "round": current_round,
        "speaker_role": "GOV_AGENT",
        "event_type": event_type,
        "price": price,
        "delivery_days": days,
        "message": message,
    })

    if event_type in ["ACCEPT", "REJECT", "ESCALATE"]:
        state["next_actor"] = "END"
        shared["status"] = "ACCEPTED" if event_type == "ACCEPT" else ("ESCALATED" if event_type == "ESCALATE" else "REJECTED")
    elif current_round >= 2:
        state["next_actor"] = "END"
        shared["status"] = "NEGOTIATING"
    else:
        state["next_actor"] = "VENDOR_AGENT"

    return state
