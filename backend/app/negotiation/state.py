"""
state.py - Type definitions and state representations for negotiation graphs.
"""
from typing import List, Literal, TypedDict


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
    estimated_budget: float
    price_floor: float
    delivery_floor: int
    current_price: float
    current_days: int
    transcript: List[NegotiationTurn]
    final_price: float
    final_days: int
    is_fallback: bool
    status: str
    action: Literal["CONTINUE", "ACCEPT", "REJECT", "ESCALATE"]
    policy_reason: str


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
