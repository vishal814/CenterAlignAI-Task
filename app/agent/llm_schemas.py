from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

class LLMGoalUnderstanding(BaseModel):
    customer_name: Optional[str] = Field(None, description="Customer name extracted from goal")
    customer_id: Optional[str] = Field(None, description="Customer ID extracted from goal, e.g. CUST001")
    ticket_id: Optional[str] = Field(None, description="Support ticket ID if mentioned, e.g. TICKET1024")
    payment_id: Optional[str] = Field(None, description="Payment ID if mentioned, e.g. PAY9001")
    intent: str = Field(..., description="High-level operational intent")
    information_needed: List[str] = Field(
        default_factory=list,
        description="Entities and context needed to resolve this goal"
    )

class LLMPlanStep(BaseModel):
    id: int = Field(..., description="Step sequence number")
    action: str = Field(..., description="Action name")
    tool: str = Field(..., description="Allowlisted tool name to invoke")
    description: str = Field(..., description="Description of the action purpose")
    reason: str = Field(..., description="Justification based on goal and policy")

class LLMStructuredPlan(BaseModel):
    goal: str = Field(..., description="Original user goal")
    steps: List[LLMPlanStep] = Field(..., description="Ordered list of execution steps")
    strategy: str = Field(..., description="Overall strategic rationale")

class LLMNextAction(BaseModel):
    action: str = Field(..., description="Allowlisted tool name to invoke next")
    reason: str = Field(..., description="Explicit rationale connecting observation to this decision")
    arguments: Dict[str, Any] = Field(
        default_factory=dict,
        description="Typed arguments for the chosen tool"
    )
