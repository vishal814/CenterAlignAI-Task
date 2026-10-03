from pathlib import Path
from typing import Dict, Any
from app.config import settings

def read_company_policy(policy_name: str = "refund_policy") -> Dict[str, Any]:
    """
    Read enterprise policy and SOP guidelines.
    Returns the exact policy rules regarding thresholds, approvals, and verification.
    """
    policy_file = Path(settings.POLICY_FILE_PATH)
    if not policy_file.exists():
        return {
            "success": False,
            "error": f"Policy file not found at {policy_file}",
            "content": ""
        }
        
    content = policy_file.read_text(encoding="utf-8")
    return {
        "success": True,
        "policyName": policy_file.name,
        "autoRefundThreshold": settings.AUTO_REFUND_THRESHOLD,
        "currency": "INR",
        "keyRules": [
            f"Refunds <= ₹{int(settings.AUTO_REFUND_THRESHOLD)} may be processed automatically if payment is confirmed and no prior refund exists.",
            f"Refunds > ₹{int(settings.AUTO_REFUND_THRESHOLD)} require human managerial approval.",
            "Never issue duplicate refunds for completed transactions.",
            "Every completed refund must update the support ticket to 'resolved'.",
            "Every refund and ticket update must be independently verified against actual database state."
        ],
        "fullContent": content
    }
