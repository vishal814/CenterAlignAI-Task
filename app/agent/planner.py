from typing import Dict, Any, List, Optional, Tuple
from app.agent.llm import understand_goal_with_llm, create_structured_plan_with_llm
from app.agent.llm_schemas import LLMGoalUnderstanding, LLMStructuredPlan
from app.tools.registry import tool_registry

def plan_and_understand_goal(goal: str) -> Tuple[LLMGoalUnderstanding, str]:
    """
    Invokes LLM to understand the high-level goal and extract entities and requirements.
    """
    return understand_goal_with_llm(goal)

def generate_validated_plan(goal: str, context: Optional[Dict[str, Any]] = None) -> Tuple[List[Dict[str, Any]], str, List[str]]:
    """
    Generates a structured plan using LLM, then validates every step against
    allowlisted tools and deterministic safety guardrails.
    Returns: (validated_plan, decision_source, validation_notes)
    """
    ctx = context or {}
    structured_plan, source = create_structured_plan_with_llm(goal, ctx)
    validation_notes = []

    # Deterministic Plan Validation Guardrails
    validated_steps = []
    allowed_tools = set(tool_registry.get_tool_definitions_names()) | {"complete_task", "verify_refund_and_ticket"}

    for step in structured_plan.steps:
        # Check tool allowlist
        if step.tool not in allowed_tools:
            validation_notes.append(
                f"Deterministic Safety Rule: Removed disallowed tool '{step.tool}' from plan step {step.id}"
            )
            continue

        validated_steps.append({
            "id": step.id,
            "action": step.action,
            "tool": step.tool,
            "description": step.description,
            "reason": step.reason,
            "status": "pending"
        })

    # If all steps were rejected or plan was empty, generate safe default plan
    if not validated_steps:
        validation_notes.append("Deterministic Safety Rule: Generated safe default plan after validation rejected proposed steps.")
        default_steps = [
            {"id": 1, "action": "identify_customer", "tool": "search_customers", "description": "Locate customer profile", "reason": "Customer ID required", "status": "pending"},
            {"id": 2, "action": "locate_ticket", "tool": "search_tickets", "description": "Find open support ticket", "reason": "Ticket reference required", "status": "pending"},
            {"id": 3, "action": "inspect_payment", "tool": "get_payment", "description": "Inspect payment ledger", "reason": "Check payment and refund status", "status": "pending"},
            {"id": 4, "action": "consult_policy", "tool": "read_company_policy", "description": "Read refund policy SOP", "reason": "Check threshold limit", "status": "pending"},
            {"id": 5, "action": "execute_or_approve", "tool": "issue_refund", "description": "Process refund or pause for approval", "reason": "Disbursement governance", "status": "pending"},
            {"id": 6, "action": "update_ticket", "tool": "update_ticket", "description": "Update ticket notes and status", "reason": "Audit record mandate", "status": "pending"},
            {"id": 7, "action": "verify_state", "tool": "verify_refund", "description": "Independently verify ledger", "reason": "Verification required", "status": "pending"},
            {"id": 8, "action": "synthesize_evidence", "tool": "complete_task", "description": "Assemble evidence payload", "reason": "Finalize task", "status": "pending"}
        ]
        validated_steps = default_steps

    return validated_steps, source, validation_notes
