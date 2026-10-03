import pytest
import sqlite3
from app.config import settings
from app.agent.graph import run_agent_task, resume_task_after_approval
from app.db.database import get_connection

def test_scenario_1_normal_successful_refund():
    """
    Scenario 1: Rahul Sharma
    - Refund <= 5000 (2499)
    - Normal successful autonomous execution
    - Database verification: refund created, ticket resolved, independent verification passed.
    """
    goal = "Resolve Rahul Sharma's payment issue."
    state = run_agent_task(goal)

    assert state["final_status"] == "completed"
    assert state["verification"]["verified"] is True
    assert state["verification"]["refund_verified"] is True
    assert state["verification"]["ticket_verified"] is True
    assert state["retry_count"] == 0
    assert state["evidence"]["customerId"] == "CUST001"
    assert state["evidence"]["ticketId"] == "TICKET1024"
    assert state["evidence"]["refundAmount"] == 2499.0

    # Verify actual database changes in SQLite
    conn = get_connection()
    # 1. Check ticket status is 'resolved'
    ticket_row = conn.execute("SELECT status, notes FROM tickets WHERE id = 'TICKET1024'").fetchone()
    assert ticket_row["status"] == "resolved"
    assert "AI Operator" in ticket_row["notes"]

    # 2. Check payment status is 'completed'
    payment_row = conn.execute("SELECT refund_status, refund_id FROM payments WHERE id = 'PAY9001'").fetchone()
    assert payment_row["refund_status"] == "completed"
    assert payment_row["refund_id"] is not None

    # 3. Check refund table contains the record
    refund_row = conn.execute("SELECT * FROM refunds WHERE id = ?", (payment_row["refund_id"],)).fetchone()
    assert refund_row is not None
    assert refund_row["amount"] == 2499.0
    assert refund_row["customer_id"] == "CUST001"
    conn.close()

def test_scenario_2_transient_failure_and_retry():
    """
    Scenario 2: Priya Patel
    - Payment PAY9002 fails on 1st refund call with temporary_payment_service_error
    - Agent observes error, determines it is retryable, retries once, and succeeds!
    - Verifies retry count is 1 and final verification passes.
    """
    goal = "Resolve Priya Patel's payment issue."
    state = run_agent_task(goal)

    assert state["final_status"] == "completed"
    assert state["retry_count"] == 1
    assert state["verification"]["verified"] is True

    # Check execution trace reflects the failure and retry
    trace_actions = [s["action"] for s in state["trace"]]
    assert "issue_refund" in trace_actions
    assert "retry_issue_refund" in trace_actions

    # Check DB state
    conn = get_connection()
    ticket_row = conn.execute("SELECT status FROM tickets WHERE id = 'TICKET1025'").fetchone()
    assert ticket_row["status"] == "resolved"

    pay_row = conn.execute("SELECT refund_status, refund_id FROM payments WHERE id = 'PAY9002'").fetchone()
    assert pay_row["refund_status"] == "completed"
    assert pay_row["refund_id"] is not None
    conn.close()

def test_scenario_3_human_approval_flow_approved():
    """
    Scenario 3: Amit Kumar
    - Amount ₹8500 > ₹5000 threshold
    - Agent pauses for human approval
    - Task state preserved
    - Manager approves -> resumes state -> issues refund -> verifies.
    """
    goal = "Resolve Amit Kumar's payment issue."
    state = run_agent_task(goal)

    # Must pause at approval gate
    assert state["final_status"] == "paused_for_approval"
    assert state["approval_required"] is True
    assert state["approval_status"] == "pending"
    assert state["approval_id"] is not None

    # Check approval record in DB
    conn = get_connection()
    app_row = conn.execute("SELECT * FROM approvals WHERE id = ?", (state["approval_id"],)).fetchone()
    assert app_row is not None
    assert app_row["amount"] == 8500.0
    assert app_row["status"] == "pending"
    conn.close()

    # Now simulate human manager approving via API/resumption
    resumed = resume_task_after_approval(state["task_id"], approved=True, decision_notes="Approved by Finance Lead")
    assert resumed["final_status"] == "completed"
    assert resumed["approval_status"] == "approved"
    assert resumed["verification"]["verified"] is True

    # Confirm refund was executed in DB
    conn = get_connection()
    pay_row = conn.execute("SELECT refund_status, refund_id FROM payments WHERE id = 'PAY9012'").fetchone()
    assert pay_row["refund_status"] == "completed"
    ticket_row = conn.execute("SELECT status FROM tickets WHERE id = 'TICKET1030'").fetchone()
    assert ticket_row["status"] == "resolved"
    conn.close()

def test_scenario_3_human_approval_flow_rejected():
    """
    Scenario 3 variant: Amit Kumar
    - Manager rejects the approval request
    - System stops safely, records rejection, updates ticket to closed, does NOT issue refund.
    """
    goal = "Resolve Amit Kumar's payment issue."
    state = run_agent_task(goal)
    assert state["final_status"] == "paused_for_approval"

    resumed = resume_task_after_approval(state["task_id"], approved=False, decision_notes="Rejected: Policy non-compliance")
    assert resumed["final_status"] == "rejected_by_human"
    assert resumed["approval_status"] == "rejected"

    # Confirm NO refund was issued in DB
    conn = get_connection()
    pay_row = conn.execute("SELECT refund_status, refund_id FROM payments WHERE id = 'PAY9012'").fetchone()
    assert pay_row["refund_status"] == "none"
    assert pay_row["refund_id"] is None

    ticket_row = conn.execute("SELECT status, notes FROM tickets WHERE id = 'TICKET1030'").fetchone()
    assert ticket_row["status"] == "closed"
    assert "Rejected" in ticket_row["notes"]
    conn.close()

def test_scenario_4_duplicate_refund_prevention():
    """
    Scenario 4: Neha Verma
    - Payment PAY9025 was already refunded under REF7701
    - Agent must NOT issue a second refund
    - Updates ticket with existing refund information and verifies.
    """
    goal = "Resolve Neha Verma's payment issue."
    state = run_agent_task(goal)

    assert state["final_status"] == "completed"
    assert state["verification"]["verified"] is True
    assert state["verification"]["refund_verified"] is True
    # The refund ID should remain REF7701 (no new refund generated)
    assert state["payment"]["refund_id"] == "REF7701"

    # Confirm DB contains exactly 1 refund record for PAY9025
    conn = get_connection()
    refund_count = conn.execute("SELECT COUNT(*) FROM refunds WHERE payment_id = 'PAY9025'").fetchone()[0]
    assert refund_count == 1
    conn.close()

def test_scenario_5_invalid_payment_status():
    """
    Scenario 5: Vikram Singh
    - Payment PAY9033 has status 'failed' (deducted from bank, but not charged in system)
    - Agent checks policy, realizes uncharged payment cannot be refunded, halts safely.
    """
    goal = "Resolve Vikram Singh's payment issue."
    state = run_agent_task(goal)

    assert state["final_status"] == "failed"
    assert "cannot be refunded" in state["summary"]

def test_scenario_6_unknown_customer():
    """
    Scenario 6: Unknown Customer
    - Customer not found in enterprise directory
    - Safe stop, reports clear error.
    """
    goal = "Resolve NonExistentPerson's payment issue."
    state = run_agent_task(goal)

    assert state["final_status"] == "failed"
    assert "No customer found" in state["summary"]

def test_scenario_7_unknown_payment():
    """
    Scenario 7: Ananya Rao (ticket has non-existent payment ID PAY9999)
    - Safe stop, reports missing payment record in ledger.
    """
    goal = "Resolve Ananya Rao's payment issue."
    state = run_agent_task(goal)

    assert state["final_status"] == "failed"
    assert "PAY9999" in state["summary"]
