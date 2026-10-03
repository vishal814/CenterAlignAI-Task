from pydantic import BaseModel, Field
from typing import Optional

class Payment(BaseModel):
    id: str = Field(..., description="Unique payment ID, e.g., PAY9001")
    customer_id: str = Field(..., description="Customer ID")
    amount: float = Field(..., description="Payment amount in INR")
    currency: str = Field("INR", description="Payment currency")
    status: str = Field("charged", description="Payment status: charged, pending, failed")
    refund_status: str = Field("none", description="Refund status: none, pending_approval, completed, failed")
    refund_id: Optional[str] = Field(None, description="Refund transaction ID if refunded")
    refund_reason: Optional[str] = Field(None, description="Reason for refund")
    created_at: str
    updated_at: str

class RefundRequest(BaseModel):
    reason: str = Field(..., description="Reason for the refund request")
    amount: Optional[float] = Field(None, description="Optional partial refund amount; defaults to full amount")

class RefundRecord(BaseModel):
    id: str
    payment_id: str
    customer_id: str
    amount: float
    status: str
    reason: str
    created_at: str
