import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, ConfigDict, Field


# --- USER SCHEMAS ---
class UserBase(BaseModel):
    email: str
    full_name: str
    role: str
    department: str


class UserCreate(UserBase):
    password: str


class UserOut(UserBase):
    id: int
    model_config = ConfigDict(from_attributes=True)


class Token(BaseModel):
    access_token: str
    token_type: str
    user: UserOut


class TokenData(BaseModel):
    email: Optional[str] = None
    role: Optional[str] = None


class LoginRequest(BaseModel):
    username: str
    password: str


# --- VENDOR SCHEMAS ---
class VendorPerformanceOut(BaseModel):
    id: int
    vendor_id: int
    metric_type: str
    value: float
    recorded_at: datetime.datetime
    notes: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)


class VendorBase(BaseModel):
    name: str
    contact_email: str
    phone: str
    avg_delivery_days: int
    reliability_score: float
    pricing_tier: str
    specialties: Optional[str] = None
    status: str = "Active"
    is_local_vendor: Optional[bool] = False
    is_incubator: Optional[bool] = False
    local_proximity_km: Optional[float] = 15.0


class VendorOut(VendorBase):
    id: int
    avg_performance_score: Optional[float] = None
    model_config = ConfigDict(from_attributes=True)


# --- VENDOR BID & SCORING SCHEMAS ---
class ScoreBreakdown(BaseModel):
    price_score: float
    delivery_score: float
    reliability_score: float
    history_score: float
    total_score: float
    price_variance_pct: float
    nearshoring_bonus: Optional[float] = 0.0


class VendorBidOut(BaseModel):
    id: int
    vendor_id: int
    pr_id: int
    quoted_price: float
    original_quoted_price: Optional[float] = None
    delivery_days: int
    original_delivery_days: Optional[int] = None
    notes: Optional[str] = None
    bid_score: float
    negotiation_transcript: Optional[str] = None
    vendor: Optional[VendorOut] = None
    model_config = ConfigDict(from_attributes=True)


class VendorRecommendation(BaseModel):
    bid_id: int
    vendor_id: int
    vendor_name: str
    pricing_tier: str
    contact_email: str
    quoted_price: float
    original_quoted_price: Optional[float] = None
    estimated_budget: float
    delivery_days: int
    original_delivery_days: Optional[int] = None
    avg_delivery_days: int
    reliability_score: float
    history_score_raw: float
    notes: Optional[str] = None
    scores: ScoreBreakdown
    rank: int
    is_local_vendor: Optional[bool] = False
    is_incubator: Optional[bool] = False
    local_proximity_km: Optional[float] = 15.0
    negotiation_transcript: Optional[List[Dict[str, Any]]] = None


class RecommendationsResponse(BaseModel):
    pr_id: int
    pr_title: str
    estimated_budget: float
    urgency: str
    department: str
    recommendations: List[VendorRecommendation]


# --- AUTONOMOUS NEGOTIATION SCHEMAS ---
class NegotiationTurnOut(BaseModel):
    round: int
    speaker: str
    speaker_role: str  # "buyer" | "vendor"
    message: str
    offered_price: float
    offered_days: int
    is_fallback: bool = False


class VendorNegotiationResultOut(BaseModel):
    vendor_id: int
    vendor_name: str
    pricing_tier: str
    original_price: float
    negotiated_price: float
    original_days: int
    negotiated_days: int
    savings_amount: float
    savings_pct: float
    days_saved: int
    status: str  # "completed" | "held"
    transcript: List[NegotiationTurnOut]
    updated_score: Optional[float] = None


class NegotiationResponse(BaseModel):
    pr_id: int
    pr_title: str
    estimated_budget: float
    total_initial_spend: float
    total_negotiated_spend: float
    total_savings: float
    total_savings_pct: float
    top_vendor_id: int
    top_vendor_name: str
    results: List[VendorNegotiationResultOut]
    recommendations: List[VendorRecommendation]


# --- APPROVAL WORKFLOW SCHEMAS ---
class ApprovalWorkflowOut(BaseModel):
    id: int
    pr_id: int
    approver_id: Optional[int] = None
    triggered_rule: str
    status: str
    comment: Optional[str] = None
    created_at: datetime.datetime
    actioned_at: Optional[datetime.datetime] = None
    approver: Optional[UserOut] = None
    model_config = ConfigDict(from_attributes=True)


class ApprovalActionRequest(BaseModel):
    action: str = Field(..., pattern="^(Approved|Rejected)$")
    comment: Optional[str] = None
    vendor_id: Optional[int] = None


# --- PURCHASE ORDER SCHEMAS ---
class PurchaseOrderOut(BaseModel):
    id: int
    pr_id: int
    vendor_id: int
    po_number: str
    total_amount: float
    status: str
    pdf_url: str
    netsuite_internal_id: Optional[str] = "NS-REC-10482"
    netsuite_sync_status: Optional[str] = "Synced (SuiteTalk REST)"
    netsuite_subsidiary: Optional[str] = "TechCorp Americas (Sub 01)"
    netsuite_gl_account: Optional[str] = "6010 - Direct Sourcing & Material CapEx"
    created_at: datetime.datetime
    vendor: Optional[VendorOut] = None
    model_config = ConfigDict(from_attributes=True)


class NetSuiteSyncResponse(BaseModel):
    po_id: int
    po_number: str
    netsuite_internal_id: str
    sync_status: str
    subsidiary: str
    gl_account: str
    currency: str = "USD"
    three_way_match_status: str
    suitetalk_rest_payload: Dict[str, Any]
    last_synced_at: datetime.datetime


class PurchaseOrderStatusUpdate(BaseModel):
    new_status: str = Field(..., pattern="^(Sent|Acknowledged|Delivered)$")


# --- COMPLIANCE SCHEMAS ---
class ViolationItem(BaseModel):
    rule_name: str
    explanation: str
    severity: str = Field(default="Medium", pattern="^(Low|Medium|High)$")


class ComplianceCheckOut(BaseModel):
    id: int
    pr_id: int
    compliant: bool
    violations: List[ViolationItem] = []
    required_action: str = ""
    checked_at: datetime.datetime
    model_config = ConfigDict(from_attributes=True)


# --- PURCHASE REQUEST SCHEMAS ---
class PurchaseRequestCreate(BaseModel):
    title: str
    item_description: str
    quantity: int = Field(default=1, ge=1)
    urgency: str = Field(default="Medium", pattern="^(Low|Medium|High|Critical)$")
    department: str
    estimated_budget: float = Field(..., gt=0)


class PurchaseRequestOut(BaseModel):
    id: int
    title: str
    item_description: str
    quantity: int
    urgency: str
    status: str
    requester_id: int
    department: str
    estimated_budget: float
    created_at: datetime.datetime
    requester: Optional[UserOut] = None
    bids_count: int = 0
    assigned_approval_rule: Optional[str] = None
    assigned_approver_role: Optional[str] = None
    approval_status: Optional[str] = None
    po_number: Optional[str] = None
    winning_vendor: Optional[str] = None
    compliance: Optional[ComplianceCheckOut] = None
    model_config = ConfigDict(from_attributes=True)


class PurchaseRequestDetail(PurchaseRequestOut):
    bids: List[VendorBidOut] = []
    approval_workflows: List[ApprovalWorkflowOut] = []
    purchase_order: Optional[PurchaseOrderOut] = None


# --- AI AUDIT SCHEMAS ---
class RiskAssessment(BaseModel):
    risk_level: str  # Low | Moderate | High
    risk_factors: List[str]
    mitigation_advice: str


class AIAuditResponse(BaseModel):
    pr_id: int
    selected_vendor_name: str
    confidence_score: float  # 0 - 100
    executive_summary: str
    key_advantages: List[str]
    net_savings_estimate: float
    risk_assessment: RiskAssessment
    is_live_gemini: bool = False


# --- DASHBOARD SCHEMAS ---
class SpendByDepartment(BaseModel):
    department: str
    amount: float
    pr_count: int


class VendorScoreSummary(BaseModel):
    vendor_name: str
    pricing_tier: str
    reliability: float
    avg_delivery_days: int
    overall_score: float


class MonthlySpendItem(BaseModel):
    month: str
    spend: float
    count: int


class DashboardMetrics(BaseModel):
    total_prs: int
    pending_approvals: int
    total_approved_pos: int
    total_spend: float
    avg_vendor_reliability: float
    three_way_match_verified: int
    spend_by_department: List[SpendByDepartment]
    vendor_performance_matrix: List[VendorScoreSummary]
    monthly_spend_flow: List[MonthlySpendItem]
    recent_prs: List[PurchaseRequestOut]
