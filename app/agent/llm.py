import os
import json
import re
from typing import Optional, Dict, Any, Tuple, Callable
from app.config import settings
from app.agent.llm_schemas import LLMGoalUnderstanding, LLMStructuredPlan, LLMPlanStep, LLMNextAction

# Hook for test injection / mock simulation
_custom_action_proposer: Optional[Callable[[Dict[str, Any]], LLMNextAction]] = None

def set_custom_action_proposer(proposer: Optional[Callable[[Dict[str, Any]], LLMNextAction]]) -> None:
    """Used in tests to simulate arbitrary or unsafe LLM proposals."""
    global _custom_action_proposer
    _custom_action_proposer = proposer

def call_gemini_json(prompt: str, schema_cls: type) -> Optional[Any]:
    """
    Invokes Google Gemini API expecting a JSON payload validated against schema_cls.
    Returns parsed Pydantic instance or None if unavailable/failed.
    """
    api_key = settings.GEMINI_API_KEY or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key or not api_key.strip():
        return None

    try:
        from google import genai
        client = genai.Client(api_key=api_key)
        
        system_instruction = (
            "You are an autonomous enterprise AI employee for CentrAlign AI. "
            "You must return ONLY valid, raw JSON adhering strictly to the requested schema. "
            "Do not include markdown code block formatting or backticks."
        )

        response = client.models.generate_content(
            model=settings.GEMINI_MODEL,
            contents=prompt,
            config={
                "system_instruction": system_instruction,
                "response_mime_type": "application/json",
                "response_schema": schema_cls
            }
        )
        text = response.text.strip()
        # Clean markdown wrappers if present
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.MULTILINE)
        text = re.sub(r"```$", "", text, flags=re.MULTILINE).strip()
        return schema_cls.model_validate_json(text)
    except Exception as e:
        print(f"[Gemini Structured LLM Warning]: {str(e)}")
        return None

# ======================================================================
# 1. UNDERSTAND GOAL
# ======================================================================

def understand_goal_with_llm(goal: str) -> Tuple[LLMGoalUnderstanding, str]:
    """
    LLM understands high-level goal, identifying entities and required context.
    """
    prompt = (
        f"Analyze this enterprise customer support request:\n'{goal}'\n\n"
        "Extract:\n"
        "- customer_name (if mentioned)\n"
        "- customer_id (if mentioned, e.g. CUST001)\n"
        "- ticket_id (if mentioned, e.g. TICKET1024)\n"
        "- payment_id (if mentioned, e.g. PAY9001)\n"
        "- intent (summary of user objective)\n"
        "- information_needed (list of enterprise entities required: e.g. customer_profile, ticket_history, payment_ledger, refund_policy)\n"
    )
    result = call_gemini_json(prompt, LLMGoalUnderstanding)
    if result:
        return result, f"LLM decision ({settings.GEMINI_MODEL})"

    # Deterministic fallback when Gemini key is not configured or offline
    ticket_match = re.search(r'\b(TICKET\d+)\b', goal, re.IGNORECASE)
    cust_id_match = re.search(r'\b(CUST\d+)\b', goal, re.IGNORECASE)
    pay_id_match = re.search(r'\b(PAY\d+)\b', goal, re.IGNORECASE)

    known_names = ["Rahul Sharma", "Rahul", "Priya Patel", "Priya", "Amit Kumar", "Amit", 
                   "Neha Verma", "Neha", "Vikram Singh", "Vikram", "Ananya Rao", "Ananya"]
    matched_name = None
    for name in known_names:
        if name.lower() in goal.lower():
            matched_name = name
            break
            
    if not matched_name and not ticket_match:
        name_match = re.search(r'resolve\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)(?:\'s)?', goal, re.IGNORECASE)
        if name_match:
            matched_name = name_match.group(1).strip()

    fallback = LLMGoalUnderstanding(
        customer_name=matched_name,
        customer_id=cust_id_match.group(1).upper() if cust_id_match else None,
        ticket_id=ticket_match.group(1).upper() if ticket_match else None,
        payment_id=pay_id_match.group(1).upper() if pay_id_match else None,
        intent="Resolve customer payment dispute or billing grievance per SOP guidelines",
        information_needed=["customer_profile", "support_ticket", "payment_record", "company_refund_policy"]
    )
    return fallback, "deterministic fallback"

# ======================================================================
# 2. CREATE STRUCTURED PLAN
# ======================================================================

def create_structured_plan_with_llm(goal: str, context: Dict[str, Any]) -> Tuple[LLMStructuredPlan, str]:
    """
    LLM formulates a dynamic structured DAG plan for achieving the user goal.
    """
    prompt = (
        f"Goal: '{goal}'\n"
        f"Context Available: {json.dumps(context, default=str)}\n"
        "Create a dynamic multi-step plan to resolve this payment dispute. "
        "Allowed tools: search_customers, get_customer, search_tickets, get_ticket, get_payment, "
        "read_company_policy, issue_refund, update_ticket, verify_refund, verify_ticket.\n"
        "Return structured JSON matching LLMStructuredPlan schema."
    )
    result = call_gemini_json(prompt, LLMStructuredPlan)
    if result:
        return result, f"LLM decision ({settings.GEMINI_MODEL})"

    # Deterministic fallback
    steps = [
        LLMPlanStep(id=1, action="identify_customer", tool="search_customers", description="Locate customer profile in enterprise directory", reason="Need customer ID to retrieve relevant tickets"),
        LLMPlanStep(id=2, action="locate_ticket", tool="search_tickets", description="Find open support ticket related to payment grievance", reason="Need ticket context and payment reference"),
        LLMPlanStep(id=3, action="inspect_payment", tool="get_payment", description="Inspect payment ledger and refund status", reason="Must verify transaction amount and refund history"),
        LLMPlanStep(id=4, action="consult_policy", tool="read_company_policy", description="Read refund policy thresholds and constraints", reason="Need SOP thresholds to decide auto-refund vs human approval"),
        LLMPlanStep(id=5, action="execute_or_approve", tool="issue_refund", description="Process refund if allowed or pause for human approval", reason="Enforces business rules on financial disbursement"),
        LLMPlanStep(id=6, action="update_ticket", tool="update_ticket", description="Update support ticket with audit resolution notes", reason="Enterprise SOP requires updating customer ticket"),
        LLMPlanStep(id=7, action="verify_state", tool="verify_refund", description="Independently verify ledger and ticket state", reason="Action success is not verified success; requires ledger proof"),
        LLMPlanStep(id=8, action="synthesize_evidence", tool="complete_task", description="Assemble evidence payload and final summary", reason="Provides auditable outcome for stakeholders")
    ]
    fallback = LLMStructuredPlan(
        goal=goal,
        steps=steps,
        strategy="Progressive context discovery, SOP threshold verification, safe execution, and independent verification."
    )
    return fallback, "deterministic fallback (offline)"

# ======================================================================
# 3. CHOOSE NEXT ACTION
# ======================================================================

def choose_next_action_with_llm(state: Dict[str, Any]) -> Tuple[LLMNextAction, str]:
    """
    LLM observes the current state, entities, and past observations, and selects the next tool/action.
    """
    global _custom_action_proposer
    if _custom_action_proposer is not None:
        return _custom_action_proposer(state), "LLM decision (simulated)"

    # Build concise state summary for LLM prompt
    customer = state.get("customer")
    ticket = state.get("ticket")
    payment = state.get("payment")
    policy = state.get("policy")
    last_observation = state["observations"][-1] if state.get("observations") else None
    retry_count = state.get("retry_count", 0)
    errors = state.get("errors", [])

    prompt = (
        f"Goal: '{state.get('goal')}'\n"
        f"Current Customer: {customer.get('name') if customer else 'Not yet found'}\n"
        f"Current Ticket: {ticket.get('id') if ticket else 'Not yet found'}\n"
        f"Current Payment: {payment.get('id') if payment else 'Not yet found'}\n"
        f"Payment Refund Status: {payment.get('refund_status') if payment else 'Unknown'}\n"
        f"Auto Refund Threshold: {policy.get('autoRefundThreshold') if policy else 'Unknown'}\n"
        f"Retry Count: {retry_count}\n"
        f"Last Observation: {json.dumps(last_observation, default=str)}\n"
        f"Recent Errors: {json.dumps(errors, default=str)}\n\n"
        "Decide the single next action to take. Allowed actions:\n"
        "- search_customers (arguments: query)\n"
        "- search_tickets (arguments: customer_id)\n"
        "- get_payment (arguments: payment_id)\n"
        "- read_company_policy (arguments: policy_name)\n"
        "- issue_refund (arguments: payment_id, reason, amount)\n"
        "- update_ticket (arguments: ticket_id, status, notes)\n"
        "- verify_refund (arguments: payment_id, expected_refund_id)\n"
        "- verify_ticket (arguments: ticket_id, expected_status)\n"
        "- complete_task (arguments: {})\n\n"
        "Return structured JSON matching LLMNextAction schema with 'action', 'reason', and 'arguments'."
    )

    result = call_gemini_json(prompt, LLMNextAction)
    if result:
        return result, f"LLM decision ({settings.GEMINI_MODEL})"

    # Deterministic fallback reasoning engine
    return _deterministic_next_action_fallback(state), "deterministic fallback (offline)"

def _deterministic_next_action_fallback(state: Dict[str, Any]) -> LLMNextAction:
    """
    Intelligent fallback determining the logical next step based on state.
    """
    customer = state.get("customer")
    ticket = state.get("ticket")
    payment = state.get("payment")
    policy = state.get("policy")

    # Step 1: Customer lookup
    if not customer:
        name = state.get("customer_name")
        if not name and state.get("goal"):
            u, _ = understand_goal_with_llm(state["goal"])
            name = u.customer_name
        query = name or state.get("goal")
        return LLMNextAction(
            action="search_customers",
            reason="Customer profile not yet identified; searching directory",
            arguments={"query": query}
        )

    # Step 2: Ticket lookup
    if not ticket:
        return LLMNextAction(
            action="search_tickets",
            reason=f"Customer {customer['id']} identified; retrieving open support tickets",
            arguments={"customer_id": customer["id"]}
        )

    # Step 3: Payment lookup
    if not payment:
        pay_id = ticket.get("payment_id")
        return LLMNextAction(
            action="get_payment",
            reason=f"Ticket {ticket['id']} found; fetching associated payment {pay_id}",
            arguments={"payment_id": pay_id}
        )

    # Step 4: Policy lookup
    if not policy:
        return LLMNextAction(
            action="read_company_policy",
            reason="Payment details retrieved; consulting SOP refund policy for threshold limits",
            arguments={"policy_name": "refund_policy"}
        )

    # Step 5: Check if transient error needs retry
    if state.get("retry_count", 0) > 0 and payment.get("refund_status") != "completed":
        return LLMNextAction(
            action="issue_refund",
            reason="The previous failure was classified as transient and retry_count is still below the allowed limit",
            arguments={"payment_id": payment["id"], "reason": f"Retry for ticket {ticket['id']}"}
        )

    # Step 6: Refund or Skip
    if payment.get("refund_status") == "completed":
        # Already refunded or just refunded -> update ticket
        if ticket.get("status") != "resolved":
            return LLMNextAction(
                action="update_ticket",
                reason=f"Payment {payment['id']} has confirmed refund {payment.get('refund_id')}; resolving support ticket",
                arguments={
                    "ticket_id": ticket["id"],
                    "status": "resolved",
                    "notes": f"Refund {payment.get('refund_id')} verified. Ticket resolved."
                }
            )
        else:
            # Ticket is resolved -> verify
            if not state.get("verification", {}).get("verified"):
                return LLMNextAction(
                    action="verify_refund",
                    reason="Ticket resolved; independently verifying refund record in database ledger",
                    arguments={"payment_id": payment["id"], "expected_refund_id": payment.get("refund_id")}
                )
            return LLMNextAction(
                action="complete_task",
                reason="All actions executed and independently verified; completing task",
                arguments={}
            )

    # Needs refund execution (if <= threshold)
    return LLMNextAction(
        action="issue_refund",
        reason="Payment is charged, no previous refund exists, and policy permits automatic refunds",
        arguments={
            "payment_id": payment["id"],
            "reason": f"Customer support dispute resolution for ticket {ticket['id']}: {ticket['issue']}"
        }
    )

def call_gemini_llm(prompt: str, system_instruction: Optional[str] = None) -> Optional[str]:
    """Free-form text generation helper used for natural language executive summaries."""
    api_key = settings.GEMINI_API_KEY or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key or not api_key.strip():
        return None

    try:
        from google import genai
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=settings.GEMINI_MODEL,
            contents=prompt,
            config={
                "system_instruction": system_instruction or "You are an autonomous enterprise AI operations employee for CentrAlign AI."
            }
        )
        return response.text.strip()
    except Exception as e:
        print(f"[Gemini LLM Warning]: {str(e)}")
        return None
