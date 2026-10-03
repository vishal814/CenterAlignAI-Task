import uuid
import datetime
from typing import Dict, Any, List, Optional, Tuple
from app.agent.state import AgentState, TraceStep
from app.agent.planner import plan_and_understand_goal, generate_validated_plan
from app.agent.llm import choose_next_action_with_llm, call_gemini_llm
from app.agent.llm_schemas import LLMNextAction
from app.agent.verifier import perform_independent_verification
from app.tools.registry import tool_registry
from app.db.database import get_connection
from app.config import settings

def append_trace(
    state: AgentState,
    phase: str,
    action: str,
    status: str,
    details: str,
    decision_source: str = "deterministic safety rule",
    reasoning: Optional[str] = None,
    input_data: Optional[Dict[str, Any]] = None,
    output_data: Optional[Dict[str, Any]] = None
) -> None:
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    step_id = len(state["trace"]) + 1
    step: TraceStep = {
        "step_id": step_id,
        "timestamp": now,
        "phase": phase,
        "action": action,
        "status": status,
        "decision_source": decision_source,
        "reasoning": reasoning,
        "details": details,
        "input_data": input_data or {},
        "output_data": output_data or {}
    }
    state["trace"].append(step)

# ======================================================================
# 1. UNDERSTAND GOAL NODE
# ======================================================================

def understand_goal_node(state: AgentState) -> AgentState:
    """
    LLM understands high-level goal, identifying entities and required context.
    """
    goal = state["goal"]
    append_trace(
        state,
        phase="understand",
        action="parse_goal",
        status="running",
        decision_source="deterministic safety rule",
        details=f"Analyzing high-level goal: '{goal}'",
        input_data={"goal": goal}
    )

    understanding, source = plan_and_understand_goal(goal)
    
    # Store extracted entities into state
    state["goal"] = goal
    state["customer_name"] = understanding.customer_name
    state["current_step"] = "understand_goal"
    state["current_step_index"] = 0

    # Generate initial validated plan
    plan_steps, plan_source, val_notes = generate_validated_plan(goal, {"entities": understanding.dict()})
    state["plan"] = plan_steps

    details = (
        f"Goal parsed via {source}. Intent: {understanding.intent}. "
        f"Entities: Customer '{understanding.customer_name}', Ticket '{understanding.ticket_id}'. "
        f"Required context: {', '.join(understanding.information_needed)}"
    )
    if val_notes:
        details += f" | {'; '.join(val_notes)}"

    append_trace(
        state,
        phase="understand",
        action="parse_goal",
        status="success",
        decision_source=source,
        reasoning=f"Identified intent '{understanding.intent}' requiring {understanding.information_needed}",
        details=details,
        output_data=understanding.dict()
    )
    return state

# ======================================================================
# 2. GATHER CONTEXT NODE (Customer, Ticket, Payment, Policy)
# ======================================================================

def gather_context_node(state: AgentState) -> AgentState:
    """
    Progressively gathers context from enterprise systems based on LLM next-action proposals,
    validated by deterministic security allowlists.
    """
    goal = state["goal"]
    
    # 1. Search Customer
    action_prop, src = choose_next_action_with_llm(state)
    append_trace(
        state,
        phase="gather_context",
        action=action_prop.action,
        status="running",
        decision_source=src,
        reasoning=action_prop.reason,
        details=f"Proposed action: {action_prop.action} ({action_prop.reason})",
        input_data=action_prop.arguments
    )

    cust_query = action_prop.arguments.get("query") or state.get("customer_name") or goal
    cust_res = tool_registry.execute("search_customers", query=cust_query)
    
    if cust_res.get("success") and cust_res.get("count", 0) > 0:
        customer = cust_res["customers"][0]
        state["customer"] = customer
        state["observations"].append({"action": "search_customers", "customer_id": customer["id"], "name": customer["name"]})
        state["executed_actions"].append({"action": "search_customers", "result": customer})
        append_trace(
            state, phase="gather_context", action="search_customers", status="success",
            decision_source=src,
            details=f"Customer identified: {customer['name']} (ID: {customer['id']}, Tier: {customer['tier']})",
            output_data=customer
        )
    else:
        err = f"No customer found matching query '{cust_query}'"
        state["errors"].append({"step": "search_customers", "error": err})
        append_trace(state, phase="gather_context", action="search_customers", status="failed",
                     decision_source="deterministic safety rule", details=err)
        state["final_status"] = "failed"
        state["summary"] = f"Unable to proceed: {err}."
        return state

    # 2. Search Ticket
    action_prop, src = choose_next_action_with_llm(state)
    append_trace(
        state, phase="gather_context", action=action_prop.action, status="running",
        decision_source=src, reasoning=action_prop.reason,
        details=f"Proposed action: {action_prop.action} ({action_prop.reason})",
        input_data=action_prop.arguments
    )
    ticket_res = tool_registry.execute("search_tickets", customer_id=state["customer"]["id"])
    if ticket_res.get("success") and ticket_res.get("count", 0) > 0:
        ticket = ticket_res["tickets"][0]
        state["ticket"] = ticket
        state["observations"].append({"action": "search_tickets", "ticket_id": ticket["id"], "issue": ticket["issue"]})
        state["executed_actions"].append({"action": "search_tickets", "result": ticket})
        append_trace(
            state, phase="gather_context", action="search_tickets", status="success",
            decision_source=src,
            details=f"Found support ticket: {ticket['id']} (Issue: '{ticket['issue']}', Status: '{ticket['status']}')",
            output_data=ticket
        )
    else:
        err = f"No support ticket found for customer {state['customer']['id']}"
        state["errors"].append({"step": "search_tickets", "error": err})
        append_trace(state, phase="gather_context", action="search_tickets", status="failed",
                     decision_source="deterministic safety rule", details=err)
        state["final_status"] = "failed"
        state["summary"] = f"Unable to proceed: {err}."
        return state

    # 3. Fetch Payment
    action_prop, src = choose_next_action_with_llm(state)
    append_trace(
        state, phase="gather_context", action=action_prop.action, status="running",
        decision_source=src, reasoning=action_prop.reason,
        details=f"Proposed action: {action_prop.action} ({action_prop.reason})",
        input_data=action_prop.arguments
    )
    payment_id = state["ticket"].get("payment_id")
    if payment_id:
        pay_res = tool_registry.execute("get_payment", payment_id=payment_id)
        if pay_res.get("success") and pay_res.get("payment"):
            payment = pay_res["payment"]
            state["payment"] = payment
            state["observations"].append({"action": "get_payment", "payment_id": payment["id"], "amount": payment["amount"], "status": payment["status"]})
            state["executed_actions"].append({"action": "get_payment", "result": payment})
            append_trace(
                state, phase="gather_context", action="get_payment", status="success",
                decision_source=src,
                details=f"Retrieved payment: {payment['id']} (Amount: ₹{payment['amount']}, Status: {payment['status']}, RefundStatus: {payment['refund_status']})",
                output_data=payment
            )
        else:
            err = f"Payment record '{payment_id}' not found in database ledger"
            state["errors"].append({"step": "get_payment", "error": err})
            append_trace(state, phase="gather_context", action="get_payment", status="failed",
                         decision_source="deterministic safety rule", details=err)
            state["final_status"] = "failed"
            state["summary"] = f"Unable to proceed: {err}."
            return state
    else:
        err = f"Ticket {state['ticket']['id']} has no associated payment ID"
        state["errors"].append({"step": "get_payment", "error": err})
        append_trace(state, phase="gather_context", action="get_payment", status="failed",
                     decision_source="deterministic safety rule", details=err)
        state["final_status"] = "failed"
        state["summary"] = f"Unable to proceed: {err}."
        return state

    # 4. Read Policy / SOP
    action_prop, src = choose_next_action_with_llm(state)
    append_trace(
        state, phase="gather_context", action=action_prop.action, status="running",
        decision_source=src, reasoning=action_prop.reason,
        details=f"Proposed action: {action_prop.action} ({action_prop.reason})",
        input_data=action_prop.arguments
    )
    policy_res = tool_registry.execute("read_company_policy")
    state["policy"] = policy_res
    state["observations"].append({"action": "read_company_policy", "autoRefundThreshold": policy_res.get("autoRefundThreshold")})
    state["executed_actions"].append({"action": "read_company_policy", "result": policy_res})
    append_trace(
        state, phase="gather_context", action="read_company_policy", status="success",
        decision_source=src,
        details=f"Policy loaded. Auto-refund threshold: ₹{policy_res.get('autoRefundThreshold', 5000)}",
        output_data={"autoRefundThreshold": policy_res.get("autoRefundThreshold")}
    )

    return state

# ======================================================================
# 3. PLAN & POLICY EVALUATION NODE
# ======================================================================

def plan_node(state: AgentState) -> AgentState:
    """
    Evaluates discovered context against enterprise SOPs.
    Deterministic safety rules guarantee thresholds, duplicate checks, and approval gates.
    """
    if state["final_status"] == "failed":
        return state

    payment = state["payment"]
    threshold = float(state["policy"].get("autoRefundThreshold", 5000.0))
    amount = float(payment["amount"])

    append_trace(
        state, phase="plan", action="evaluate_eligibility", status="running",
        decision_source="deterministic safety rule",
        details=f"Evaluating payment {payment['id']}: Amount ₹{amount}, Status '{payment['status']}', RefundStatus '{payment['refund_status']}' against threshold ₹{threshold}"
    )

    # Deterministic Guardrail 1: Duplicate Prevention
    if payment["refund_status"] == "completed":
        append_trace(
            state, phase="plan", action="evaluate_eligibility", status="success",
            decision_source="deterministic safety rule",
            details=f"Payment {payment['id']} was ALREADY refunded under Refund ID {payment.get('refund_id')}. Deterministic rule overrides execution to prevent duplicate disbursement."
        )
        state["observations"].append({
            "observation": "payment_already_refunded",
            "refund_id": payment.get("refund_id")
        })
        return state

    # Deterministic Guardrail 2: Invalid Payment Status
    if payment["status"] != "charged":
        append_trace(
            state, phase="plan", action="evaluate_eligibility", status="failed",
            decision_source="deterministic safety rule",
            details=f"Payment status is '{payment['status']}' (not 'charged'). Per SOP, refunds cannot be issued for uncharged payments."
        )
        state["final_status"] = "failed"
        state["summary"] = f"Task halted: Payment {payment['id']} has status '{payment['status']}' and cannot be refunded."
        return state

    # Deterministic Guardrail 3: Human Approval Gate (Amount > Threshold)
    if amount > threshold:
        append_trace(
            state, phase="plan", action="evaluate_eligibility", status="paused",
            decision_source="deterministic safety rule",
            details=f"Amount ₹{amount} strictly exceeds auto-approval threshold of ₹{threshold}. Deterministic rule mandates Human Manager Approval."
        )
        state["approval_required"] = True
        state["approval_status"] = "pending"
        
        # Insert approval record in DB
        app_id = f"APP{uuid.uuid4().hex[:6].upper()}"
        state["approval_id"] = app_id
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        
        conn = get_connection()
        conn.execute(
            """INSERT INTO approvals 
            (id, task_id, customer_id, customer_name, ticket_id, payment_id, amount, action, reason, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?)""",
            (
                app_id,
                state["task_id"],
                state["customer"]["id"],
                state["customer"]["name"],
                state["ticket"]["id"],
                payment["id"],
                amount,
                "issue_refund",
                f"Refund amount (₹{amount}) exceeds automatic approval threshold of ₹{threshold}",
                now
            )
        )
        conn.commit()
        conn.close()

        state["approval_details"] = {
            "approval_id": app_id,
            "amount": amount,
            "threshold": threshold,
            "reason": f"Refund amount (₹{amount}) exceeds automatic approval limit (₹{threshold})"
        }
        state["final_status"] = "paused_for_approval"
        return state

    # Normal auto-approval flow (<= threshold)
    append_trace(
        state, phase="plan", action="evaluate_eligibility", status="success",
        decision_source="deterministic safety rule",
        details=f"Amount ₹{amount} <= threshold ₹{threshold}. Autonomous approval granted per SOP."
    )
    return state

# ======================================================================
# 4. EXECUTE ACTION NODE (LLM Proposed Action -> Deterministic Validation -> Tool Execution)
# ======================================================================

def execute_action_node(state: AgentState) -> AgentState:
    """
    LLM proposes the next action. The deterministic engine validates against allowlists,
    safety rules, and retry limits before tool execution.
    """
    if state["final_status"] in ("failed", "paused_for_approval", "rejected_by_human"):
        return state

    payment = state["payment"]
    ticket = state["ticket"]
    customer = state["customer"]

    # 1. Ask LLM to propose next action
    action_prop, prop_src = choose_next_action_with_llm(state)

    # -------------------------------------------------------------
    # DETERMINISTIC SAFETY VALIDATOR
    # -------------------------------------------------------------
    # Rule A: Disallowed Tool Check
    if not tool_registry.is_allowed(action_prop.action) and action_prop.action != "complete_task":
        err_msg = f"Deterministic Safety Rule: Action '{action_prop.action}' is not in allowlisted tool registry. Rejecting proposal."
        state["errors"].append({"action": action_prop.action, "error": err_msg})
        append_trace(
            state, phase="execute", action=action_prop.action, status="failed",
            decision_source="deterministic safety rule", details=err_msg
        )
        state["final_status"] = "failed"
        state["summary"] = f"Task halted: Unsafe action '{action_prop.action}' was rejected by deterministic allowlist."
        return state

    # Rule B: Duplicate Refund Override
    if payment["refund_status"] == "completed":
        append_trace(
            state, phase="execute", action="skip_refund", status="skipped",
            decision_source="deterministic safety rule",
            reasoning="Payment already refunded; overriding to prevent duplicate financial transaction.",
            details=f"Refund skipped to prevent duplicate debit. Existing Refund ID: {payment.get('refund_id')}"
        )
        # Update ticket referencing existing refund
        update_notes = f"Verified existing refund {payment.get('refund_id')} for ₹{payment['amount']} issued previously. Ticket marked resolved."
        up_res = tool_registry.execute("update_ticket", ticket_id=ticket["id"], status="resolved", notes=update_notes)
        append_trace(
            state, phase="execute", action="update_ticket", status="success",
            decision_source="deterministic safety rule",
            details=f"Ticket {ticket['id']} updated to 'resolved' referencing existing refund {payment.get('refund_id')}",
            output_data=up_res
        )
        state["ticket"]["status"] = "resolved"
        return state

    # Rule C: Approval Enforcement (Safety guardrail preventing LLM from bypassing approval)
    threshold = float(state["policy"].get("autoRefundThreshold", 5000.0))
    if float(payment["amount"]) > threshold and state.get("approval_status") != "approved":
        override_msg = f"Deterministic Safety Rule: LLM proposed '{action_prop.action}', but ₹{payment['amount']} exceeds threshold ₹{threshold}. Forcing Human Approval Gate."
        append_trace(
            state, phase="execute", action="enforce_approval", status="paused",
            decision_source="deterministic safety rule", details=override_msg
        )
        state["approval_required"] = True
        state["final_status"] = "paused_for_approval"
        return state

    # -------------------------------------------------------------
    # EXECUTE VALIDATED ACTION: issue_refund
    # -------------------------------------------------------------
    append_trace(
        state, phase="execute", action="issue_refund", status="running",
        decision_source=prop_src,
        reasoning=action_prop.reason,
        details=f"Issuing refund of ₹{payment['amount']} for Payment ID {payment['id']} ({action_prop.reason})"
    )

    reason = action_prop.arguments.get("reason") or f"Customer support dispute resolution for ticket {ticket['id']}: {ticket['issue']}"
    refund_res = tool_registry.execute(
        "issue_refund",
        payment_id=payment["id"],
        reason=reason,
        amount=payment["amount"]
    )

    # -------------------------------------------------------------
    # OBSERVE & RECOVERY LOGIC (Transient Failure Handling)
    # -------------------------------------------------------------
    if not refund_res.get("success"):
        if refund_res.get("retryable") and state["retry_count"] < state["max_retries"]:
            state["retry_count"] += 1
            append_trace(
                state, phase="observe", action="issue_refund", status="failed",
                decision_source="recovery logic",
                details=f"Transient failure observed: {refund_res.get('error')} ({refund_res.get('message')}). Retrying (Attempt {state['retry_count']}/{state['max_retries']})...",
                output_data=refund_res
            )
            
            # Consult LLM for retry action
            retry_prop, retry_src = choose_next_action_with_llm(state)
            append_trace(
                state, phase="adapt", action="retry_issue_refund", status="running",
                decision_source="recovery logic",
                reasoning=retry_prop.reason,
                details=f"Executing automatic retry for payment {payment['id']}: {retry_prop.reason}"
            )
            retry_res = tool_registry.execute(
                "issue_refund",
                payment_id=payment["id"],
                reason=reason,
                amount=payment["amount"]
            )
            if retry_res.get("success"):
                append_trace(
                    state, phase="execute", action="issue_refund", status="retried",
                    decision_source="recovery logic",
                    details=f"Retry SUCCEEDED! Refund ID generated: {retry_res.get('refundId')}",
                    output_data=retry_res
                )
                state["executed_actions"].append({"action": "issue_refund", "result": retry_res})
                state["payment"]["refund_id"] = retry_res.get("refundId")
                state["payment"]["refund_status"] = "completed"
            else:
                err = f"Retry failed: {retry_res.get('error')}"
                state["errors"].append({"action": "issue_refund_retry", "error": err})
                append_trace(state, phase="execute", action="issue_refund", status="failed",
                             decision_source="deterministic safety rule", details=err)
                state["final_status"] = "failed"
                state["summary"] = f"Task halted: Refund execution failed after retry ({err})."
                return state
        else:
            err = f"Refund failed: {refund_res.get('error')}"
            state["errors"].append({"action": "issue_refund", "error": err})
            append_trace(state, phase="execute", action="issue_refund", status="failed",
                         decision_source="deterministic safety rule", details=err)
            state["final_status"] = "failed"
            state["summary"] = f"Task halted: Refund execution failed ({err})."
            return state
    else:
        append_trace(
            state, phase="execute", action="issue_refund", status="success",
            decision_source=prop_src,
            details=f"Refund executed successfully. Refund ID: {refund_res.get('refundId')}",
            output_data=refund_res
        )
        state["executed_actions"].append({"action": "issue_refund", "result": refund_res})
        state["payment"]["refund_id"] = refund_res.get("refundId")
        state["payment"]["refund_status"] = "completed"

    # Now update support ticket
    ref_id = state["payment"]["refund_id"]
    notes = f"Refund {ref_id} of ₹{payment['amount']} processed successfully. Resolution confirmed by AI Operator."
    append_trace(
        state, phase="execute", action="update_ticket", status="running",
        decision_source=prop_src,
        reasoning="Payment refunded successfully; updating ticket status to resolved with audit notes.",
        details=f"Updating ticket {ticket['id']} status to 'resolved'"
    )
    up_res = tool_registry.execute("update_ticket", ticket_id=ticket["id"], status="resolved", notes=notes)
    append_trace(
        state, phase="execute", action="update_ticket", status="success",
        decision_source=prop_src,
        details=f"Ticket {ticket['id']} updated to 'resolved' with resolution notes.",
        output_data=up_res
    )
    state["executed_actions"].append({"action": "update_ticket", "result": up_res})
    state["ticket"]["status"] = "resolved"

    return state

# ======================================================================
# 5. INDEPENDENT VERIFICATION NODE
# ======================================================================

def verify_node(state: AgentState) -> AgentState:
    """
    Performs independent verification strictly separate from execution actions.
    Guarantees that action success does not equal verified outcome.
    """
    if state["final_status"] in ("failed", "paused_for_approval", "rejected_by_human"):
        return state

    payment = state["payment"]
    ticket = state["ticket"]
    expected_ref_id = payment.get("refund_id")

    append_trace(
        state, phase="verify", action="independent_verification", status="running",
        decision_source="deterministic safety rule",
        details=f"Starting independent verification: Ledger check for Payment {payment['id']} and Ticket {ticket['id']}"
    )

    verif_res = perform_independent_verification(
        payment_id=payment["id"],
        ticket_id=ticket["id"],
        expected_refund_id=expected_ref_id,
        expected_ticket_status="resolved"
    )

    state["verification"] = verif_res

    if verif_res["verified"]:
        append_trace(
            state, phase="verify", action="independent_verification", status="success",
            decision_source="deterministic safety rule",
            details="INDEPENDENT VERIFICATION PASSED: Database ledger confirms refund record and ticket state is 'resolved'.",
            output_data=verif_res
        )
    else:
        err_msg = "; ".join(verif_res["errors"])
        append_trace(
            state, phase="verify", action="independent_verification", status="failed",
            decision_source="deterministic safety rule",
            details=f"INDEPENDENT VERIFICATION FAILED: {err_msg}",
            output_data=verif_res
        )
        state["final_status"] = "failed_verification"
        state["summary"] = f"Task verification failed: {err_msg}. Actions will not be marked as complete."
        return state

    return state

# ======================================================================
# 6. COMPLETE NODE
# ======================================================================

def complete_node(state: AgentState) -> AgentState:
    """
    Assembles structured evidence payload and executive summary.
    """
    if state["final_status"] in ("failed", "paused_for_approval", "rejected_by_human", "failed_verification"):
        return state

    customer = state["customer"]
    ticket = state["ticket"]
    payment = state["payment"]
    refund_id = payment.get("refund_id")
    amount = payment.get("amount")

    evidence = {
        "status": "completed",
        "customerId": customer["id"],
        "customerName": customer["name"],
        "ticketId": ticket["id"],
        "paymentId": payment["id"],
        "refundId": refund_id,
        "refundAmount": amount,
        "ticketStatus": "resolved",
        "verification": {
            "refundVerified": state["verification"].get("refund_verified", False),
            "ticketVerified": state["verification"].get("ticket_verified", False)
        }
    }
    state["evidence"] = evidence
    state["final_status"] = "completed"

    deterministic_summary = (
        f"Resolved {customer['name']}'s payment issue. "
        f"A ₹{int(amount)} refund ({refund_id}) was verified in the database ledger, "
        f"the support ticket ({ticket['id']}) was updated to resolved, "
        f"and both the refund and ticket state were independently verified."
    )

    llm_prompt = (
        f"Summarize the resolution of the following enterprise support task for management:\n"
        f"Goal: {state['goal']}\n"
        f"Customer: {customer['name']} ({customer['id']})\n"
        f"Ticket: {ticket['id']} (Issue: {ticket['issue']})\n"
        f"Refund: ₹{amount} under Refund ID {refund_id}\n"
        f"Verification: Both database ledger and support ticket status independently verified.\n"
        f"Keep the summary concise, professional, and clear."
    )
    enriched_summary = call_gemini_llm(llm_prompt)
    state["summary"] = enriched_summary if enriched_summary else deterministic_summary

    append_trace(
        state, phase="complete", action="finalize_evidence", status="success",
        decision_source="deterministic safety rule",
        details="Task completed and independently verified. Structured evidence assembled.",
        output_data=evidence
    )
    return state
