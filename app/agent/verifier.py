from typing import Dict, Any, Optional
from app.tools.registry import tool_registry

def perform_independent_verification(
    payment_id: Optional[str],
    ticket_id: Optional[str],
    expected_refund_id: Optional[str] = None,
    expected_ticket_status: str = "resolved"
) -> Dict[str, Any]:
    """
    Performs independent verification by re-querying the database ledger and support tickets.
    Guarantees that action success is strictly decoupled from verified outcome.
    """
    verification_results = {
        "refund_verified": False,
        "ticket_verified": False,
        "verified": False,
        "details": [],
        "errors": []
    }

    # 1. Verify Payment & Refund
    if payment_id:
        refund_res = tool_registry.execute(
            "verify_refund",
            payment_id=payment_id,
            expected_refund_id=expected_refund_id
        )
        if refund_res.get("verified", False):
            verification_results["refund_verified"] = True
            verification_results["details"].append(
                f"Ledger Verification Passed: Payment {payment_id} has confirmed refund {refund_res.get('refundId')} (Amount: ₹{refund_res.get('refundAmount')})"
            )
            verification_results["refund_evidence"] = refund_res
        else:
            verification_results["errors"].append(
                f"Ledger Verification FAILED: {refund_res.get('message', 'Refund record not found in database')}"
            )
    else:
        verification_results["errors"].append("Ledger Verification Skipped: No payment ID provided")

    # 2. Verify Ticket State
    if ticket_id:
        ticket_res = tool_registry.execute(
            "verify_ticket",
            ticket_id=ticket_id,
            expected_status=expected_ticket_status
        )
        if ticket_res.get("verified", False):
            verification_results["ticket_verified"] = True
            verification_results["details"].append(
                f"Ticket Verification Passed: Ticket {ticket_id} status is confirmed as '{ticket_res.get('currentStatus')}'"
            )
            verification_results["ticket_evidence"] = ticket_res
        else:
            verification_results["errors"].append(
                f"Ticket Verification FAILED: {ticket_res.get('message', 'Ticket status mismatch')}"
            )
    else:
        verification_results["errors"].append("Ticket Verification Skipped: No ticket ID provided")

    # Both must pass for overall verified status
    verification_results["verified"] = (
        verification_results["refund_verified"] and verification_results["ticket_verified"]
    )

    return verification_results
