import pytest
from app.agent.verifier import perform_independent_verification
from app.tools.registry import tool_registry

def test_independent_verification_success():
    """
    Test that verification passes when BOTH refund is confirmed in DB and ticket is resolved.
    """
    # 1. Issue refund on PAY9001
    ref = tool_registry.execute("issue_refund", payment_id="PAY9001", reason="Verification test")
    assert ref["success"] is True

    # 2. Update ticket TICKET1024 to resolved
    up = tool_registry.execute("update_ticket", ticket_id="TICKET1024", status="resolved", notes="Verified")
    assert up["success"] is True

    # 3. Independent verification
    res = perform_independent_verification(
        payment_id="PAY9001",
        ticket_id="TICKET1024",
        expected_refund_id=ref["refundId"],
        expected_ticket_status="resolved"
    )

    assert res["verified"] is True
    assert res["refund_verified"] is True
    assert res["ticket_verified"] is True
    assert len(res["errors"]) == 0

def test_independent_verification_fails_if_ticket_not_resolved():
    """
    Simulates a case where the refund succeeded, but the ticket was NOT updated to 'resolved'.
    Verification MUST FAIL. Action success is strictly decoupled from verified success.
    """
    ref = tool_registry.execute("issue_refund", payment_id="PAY9001", reason="Verification test")
    assert ref["success"] is True

    # Ticket is still 'open' in DB
    res = perform_independent_verification(
        payment_id="PAY9001",
        ticket_id="TICKET1024",
        expected_refund_id=ref["refundId"],
        expected_ticket_status="resolved"
    )

    assert res["verified"] is False
    assert res["refund_verified"] is True
    assert res["ticket_verified"] is False
    assert any("Ticket status mismatch" in err or "Current status is 'open'" in err for err in res["errors"])

def test_independent_verification_fails_if_refund_missing():
    """
    Simulates a case where the ticket was marked resolved, but NO refund was recorded in DB ledger.
    Verification MUST FAIL.
    """
    tool_registry.execute("update_ticket", ticket_id="TICKET1024", status="resolved")

    # Payment PAY9001 has not been refunded yet
    res = perform_independent_verification(
        payment_id="PAY9001",
        ticket_id="TICKET1024",
        expected_refund_id="REF_NON_EXISTENT",
        expected_ticket_status="resolved"
    )

    assert res["verified"] is False
    assert res["refund_verified"] is False
    assert res["ticket_verified"] is True
