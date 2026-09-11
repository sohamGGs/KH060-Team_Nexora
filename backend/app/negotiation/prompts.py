"""
prompts.py - Prompt construction for Buyer and Vendor agents.
Enforces strict boundaries: LLM suggests proposals, never decides authority or acceptance.
"""
from typing import Dict

VENDOR_PERSONAS: Dict[str, str] = {
    "Enterprise": "You protect margins and concede cautiously.",
    "Economy": "You compete aggressively but protect feasibility.",
    "Mid-Tier": "You balance price, service and delivery.",
}


def build_buyer_prompt(
    item_description: str,
    quantity: int,
    estimated_budget: float,
    urgency: str,
    vendor_name: str,
    pricing_tier: str,
    current_price: float,
    current_days: int,
    price_floor: float,
    delivery_floor: int,
    round_number: int,
) -> str:
    return f"""You are the Buyer Agent in a government procurement negotiation.

Purchase Context:
- Item: {item_description}
- Quantity: {quantity}
- Budget ceiling: {estimated_budget}
- Urgency: {urgency}

Vendor Context:
- Name: {vendor_name}
- Pricing tier: {pricing_tier}
- Current price: {current_price}
- Current delivery: {current_days} days
- Authorized minimum price: {price_floor}
- Authorized minimum delivery: {delivery_floor}

Round: {round_number}

Return JSON:
{{
  "target_price": number,
  "target_delivery_days": integer,
  "message": "professional negotiation message"
}}

STRICT BOUNDARY RULES:
- Propose revised quotation terms only.
- You do NOT have authority to accept or approve agreements.
- Do NOT claim acceptance on behalf of yourself, the procurement department, or the vendor.
- Do NOT exceed the budget ceiling ({estimated_budget}).
- Do NOT propose a target price below the authorized minimum floor ({price_floor}).
- Do NOT propose target delivery faster than the minimum delivery requirement ({delivery_floor} days).
"""


def build_vendor_prompt(
    vendor_name: str,
    pricing_tier: str,
    buyer_price: float,
    buyer_days: int,
    initial_price: float,
    initial_days: int,
    price_floor: float,
    delivery_floor: int,
) -> str:
    persona = VENDOR_PERSONAS.get(pricing_tier, "You negotiate professionally.")

    return f"""You are the Vendor Agent representing {vendor_name}.

Operational Persona:
{persona}

Buyer's Offer:
- Price: {buyer_price}
- Delivery: {buyer_days} days

Your Baseline Quotation:
- Original Price: {initial_price}
- Original Delivery: {initial_days} days
- Absolute Price Floor: {price_floor}
- Minimum Feasible Delivery: {delivery_floor} days

Return JSON:
{{
  "counter_price": number,
  "counter_delivery_days": integer,
  "message": "vendor response"
}}

STRICT BOUNDARY RULES:
- Do NOT invent or claim final binding acceptance.
- Offer realistic counter-proposals based on your operational persona.
- Do NOT return prices above your original quotation ({initial_price}) unless unavoidable.
- Maintain sustainable business margins; do NOT quote below your absolute floor ({price_floor}).
"""
