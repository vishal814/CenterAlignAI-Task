from pydantic import BaseModel, Field
from typing import Optional

class Customer(BaseModel):
    id: str = Field(..., description="Unique customer ID, e.g., CUST001")
    name: str = Field(..., description="Customer full name")
    email: str = Field(..., description="Customer email address")
    phone: Optional[str] = Field(None, description="Customer contact phone")
    tier: str = Field("standard", description="Customer tier: standard, pro, enterprise")
    created_at: str
