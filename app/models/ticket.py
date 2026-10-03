from pydantic import BaseModel, Field
from typing import Optional

class SupportTicket(BaseModel):
    id: str = Field(..., description="Unique ticket ID, e.g., TICKET1024")
    customer_id: str = Field(..., description="Customer ID")
    issue: str = Field(..., description="Description of the customer issue")
    payment_id: Optional[str] = Field(None, description="Associated payment ID if any")
    status: str = Field("open", description="Ticket status: open, in_progress, pending_approval, resolved, closed")
    notes: Optional[str] = Field("", description="Resolution or investigation notes")
    created_at: str
    updated_at: str

class TicketUpdate(BaseModel):
    status: Optional[str] = None
    notes: Optional[str] = None
