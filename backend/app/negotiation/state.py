
from typing import List, Literal, TypedDict, Optional
from pydantic import BaseModel

class NegotiationTurn(TypedDict):
    round: int
    speaker_role: Literal["GOV_AGENT", "VENDOR_AGENT", "GOV_HUMAN", "VENDOR_HUMAN", "SYSTEM"]
    event_type: Literal["OFFER", "MESSAGE", "ACCEPT", "REJECT", "ESCALATE"]
    price: Optional[float]
    delivery_days: Optional[int]
    message: str

class SharedState(TypedDict):
    session_id: int
    pr_id: int
    pr_title: str
    item_description: str
    quantity: int
    current_round: int
    status: str
    events: List[NegotiationTurn]

class GovAgentState(TypedDict):
    target_price: float
    max_authorized_price: float
    target_delivery: int
    max_delivery: int
    strategy: str

class VendorAgentState(TypedDict):
    target_price: float
    absolute_minimum_price: float
    feasible_delivery: int
    strategy: str

class GraphNegotiationState(TypedDict):
    shared: SharedState
    gov: GovAgentState
    vendor: VendorAgentState
    next_actor: Literal["GOV_AGENT", "VENDOR_AGENT", "END"]
