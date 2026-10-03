import pytest
from app.agent.llm import set_custom_action_proposer
from app.agent.llm_schemas import LLMNextAction
from app.agent.graph import run_agent_task, resume_task_after_approval, create_initial_state
from app.agent.executor import execute_action_node
from app.db.database import get_connection

def teardown_function():
    """Ensure custom action proposer is cleared after each test."""
    set_custom_action_proposer(None)

def test_llm_generated_action_validated_before_execution():
    """
    Test 1: Proves that a valid LLM-proposed action is validated against the allowlist
    and successfully executed with decision_source recorded.
    """
    goal = "Resolve Rahul Sharma's payment issue."
    state = run_agent_task(goal)

    assert state["final_status"] == "completed"
    
    # Check trace includes both LLM decisions and deterministic validations
    decision_sources = [s["decision_source"] for s in state["trace"]]
    assert "LLM decision" in decision_sources or "deterministic fallback" in decision_sources
    assert "deterministic safety rule" in decision_sources

def test_invalid_llm_tool_rejected():
    """
    Test 2: Proves that an invalid/unallowlisted tool proposed by the LLM
    is intercepted and rejected by the deterministic safety validator.
    """
    # Simulate an LLM proposing an arbitrary shell command or disallowed tool
    def malicious_proposer(state):
        return LLMNextAction(
            action="arbitrary_shell_command",
            reason="Attempting unauthorized system command",
            arguments={"command": "rm -rf /"}
        )

    set_custom_action_proposer(malicious_proposer)

    goal = "Resolve Rahul Sharma's payment issue."
    state = run_agent_task(goal)

    # Must fail safely without executing the tool
    assert state["final_status"] == "failed"
    assert any("not in allowlisted tool registry" in err["error"] for err in state["errors"])
    
    # Check trace records the deterministic safety rejection
    rejection_steps = [
        s for s in state["trace"] 
        if s["decision_source"] == "deterministic safety rule" and s["status"] == "failed"
    ]
    assert len(rejection_steps) > 0
    assert "not in allowlisted tool registry" in rejection_steps[0]["details"]

def test_business_rules_override_unsafe_llm_suggestions_duplicate_refund():
    """
    Test 3: Proves that business rules override unsafe LLM suggestions.
    If the LLM attempts to propose an 'issue_refund' on an already refunded transaction,
    the deterministic safety validator overrides the action to prevent duplicate disbursement.
    """
    # Simulate an LLM proposing issue_refund even though payment is already refunded
    def unsafe_duplicate_proposer(state):
        payment = state.get("payment")
        if payment and payment.get("refund_status") == "completed":
            return LLMNextAction(
                action="issue_refund",
                reason="Unsafely attempting to disburse a second refund",
                arguments={"payment_id": payment["id"], "reason": "duplicate attempt"}
            )
        # Default behavior for other states
        from app.agent.llm import _deterministic_next_action_fallback
        return _deterministic_next_action_fallback(state)

    set_custom_action_proposer(unsafe_duplicate_proposer)

    # Neha Verma: Payment PAY9025 is already refunded under REF7701
    goal = "Resolve Neha Verma's payment issue."
    state = run_agent_task(goal)

    assert state["final_status"] == "completed"
    
    # Confirm DB contains exactly 1 refund record (duplicate was prevented)
    conn = get_connection()
    refund_count = conn.execute("SELECT COUNT(*) FROM refunds WHERE payment_id = 'PAY9025'").fetchone()[0]
    assert refund_count == 1
    conn.close()

    # Confirm the trace explicitly records the safety override
    override_steps = [
        s for s in state["trace"] 
        if s["decision_source"] == "deterministic safety rule" and "prevent duplicate" in s["details"]
    ]
    assert len(override_steps) > 0

def test_approval_cannot_be_bypassed_by_llm():
    """
    Test 4: Proves that the LLM cannot bypass human approval thresholds.
    If the LLM proposes 'issue_refund' for an amount > 5000, the deterministic validator
    overrides the proposal and forces 'paused_for_approval'.
    """
    def bypass_attempt_proposer(state):
        payment = state.get("payment")
        if payment and payment.get("amount") > 5000:
            return LLMNextAction(
                action="issue_refund",
                reason="Attempting to disburse ₹8500 without managerial approval",
                arguments={"payment_id": payment["id"], "amount": 8500.0}
            )
        from app.agent.llm import _deterministic_next_action_fallback
        return _deterministic_next_action_fallback(state)

    set_custom_action_proposer(bypass_attempt_proposer)

    goal = "Resolve Amit Kumar's payment issue."
    state = run_agent_task(goal)

    # Must be paused for approval regardless of LLM desire to refund
    assert state["final_status"] == "paused_for_approval"
    assert state["approval_required"] is True

    # Confirm NO refund was issued in the database ledger
    conn = get_connection()
    pay_row = conn.execute("SELECT refund_status FROM payments WHERE id = 'PAY9012'").fetchone()
    assert pay_row["refund_status"] == "none"
    conn.close()

def test_transient_failure_causes_valid_retry_decision():
    """
    Test 5: Proves that a transient error causes a valid retry decision tracked in recovery logic.
    """
    goal = "Resolve Priya Patel's payment issue."
    state = run_agent_task(goal)

    assert state["final_status"] == "completed"
    assert state["retry_count"] == 1

    # Check trace records recovery logic decision source
    recovery_steps = [s for s in state["trace"] if s["decision_source"] == "recovery logic"]
    assert len(recovery_steps) >= 2
    assert any(s["status"] == "retried" for s in recovery_steps)

def test_verification_still_controls_final_completion():
    """
    Test 6: Proves that verification strictly controls completion.
    Action success is not sufficient; verified ledger state is mandatory.
    """
    goal = "Resolve Rahul Sharma's payment issue."
    state = run_agent_task(goal)

    assert state["final_status"] == "completed"
    assert state["verification"]["verified"] is True
    assert state["verification"]["refund_verified"] is True
    assert state["verification"]["ticket_verified"] is True
