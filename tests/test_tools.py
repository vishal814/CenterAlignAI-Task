import pytest
from app.tools.registry import tool_registry

def test_customer_tools():
    # search_customers
    res = tool_registry.execute("search_customers", query="Rahul")
    assert res["success"] is True
    assert res["count"] >= 1
    assert res["customers"][0]["id"] == "CUST001"

    # get_customer
    cust = tool_registry.execute("get_customer", customer_id="CUST001")
    assert cust["success"] is True
    assert cust["customer"]["name"] == "Rahul Sharma"

    # non-existent customer
    cust_none = tool_registry.execute("get_customer", customer_id="CUST_NON_EXISTENT")
    assert cust_none["success"] is False

def test_ticket_tools():
    # search_tickets
    res = tool_registry.execute("search_tickets", customer_id="CUST001")
    assert res["success"] is True
    assert len(res["tickets"]) >= 1

    # get_ticket
    ticket = tool_registry.execute("get_ticket", ticket_id="TICKET1024")
    assert ticket["success"] is True
    assert ticket["ticket"]["status"] == "open"

    # update_ticket
    updated = tool_registry.execute("update_ticket", ticket_id="TICKET1024", status="in_progress", notes="Test note")
    assert updated["success"] is True
    assert updated["status"] == "in_progress"

def test_payment_tools():
    # get_payment
    pay = tool_registry.execute("get_payment", payment_id="PAY9001")
    assert pay["success"] is True
    assert pay["payment"]["amount"] == 2499.0

    # issue_refund
    ref = tool_registry.execute("issue_refund", payment_id="PAY9001", reason="Unit test refund")
    assert ref["success"] is True
    assert ref["refundId"].startswith("REF")
    assert ref["amount"] == 2499.0

    # duplicate prevention
    dup = tool_registry.execute("issue_refund", payment_id="PAY9001", reason="Second attempt")
    assert dup["success"] is False
    assert dup["error"] == "duplicate_refund_prevented"

def test_policy_tools():
    policy = tool_registry.execute("read_company_policy")
    assert policy["success"] is True
    assert policy["autoRefundThreshold"] == 5000.0
    assert len(policy["keyRules"]) >= 3

def test_disallowed_tool_call():
    res = tool_registry.execute("arbitrary_shell_command", cmd="rm -rf /")
    assert res["success"] is False
    assert "not in the allowlisted tool registry" in res["error"]
