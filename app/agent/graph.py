import uuid
import datetime
from typing import Dict, Any, Optional
from langgraph.graph import StateGraph, END
from app.agent.state import AgentState
from app.agent.executor import (
    understand_goal_node,
    gather_context_node,
    plan_node,
    execute_action_node,
    verify_node,
    complete_node,
    append_trace
)
from app.tools.registry import tool_registry

# In-memory store for active tasks (can also be queried by task_id)
task_store: Dict[str, AgentState] = {}

def build_agent_graph():
    builder = StateGraph(AgentState)

    builder.add_node("understand_goal", understand_goal_node)
    builder.add_node("gather_context", gather_context_node)
    builder.add_node("plan", plan_node)
    builder.add_node("execute_action", execute_action_node)
    builder.add_node("verify", verify_node)
    builder.add_node("complete", complete_node)

    builder.set_entry_point("understand_goal")
    builder.add_edge("understand_goal", "gather_context")

    def route_after_context(state: AgentState) -> str:
        if state["final_status"] == "failed":
            return "complete"
        return "plan"

    builder.add_conditional_edges(
        "gather_context",
        route_after_context,
        {"plan": "plan", "complete": "complete"}
    )

    def route_after_plan(state: AgentState) -> str:
        if state["final_status"] == "failed":
            return "complete"
        if state["final_status"] == "paused_for_approval":
            return END
        return "execute_action"

    builder.add_conditional_edges(
        "plan",
        route_after_plan,
        {"execute_action": "execute_action", "complete": "complete", END: END}
    )

    def route_after_execute(state: AgentState) -> str:
        if state["final_status"] == "failed":
            return "complete"
        return "verify"

    builder.add_conditional_edges(
        "execute_action",
        route_after_execute,
        {"verify": "verify", "complete": "complete"}
    )

    builder.add_edge("verify", "complete")
    builder.add_edge("complete", END)

    return builder.compile()

# Global compiled graph
agent_graph = build_agent_graph()

def create_initial_state(goal: str, task_id: Optional[str] = None) -> AgentState:
    t_id = task_id or f"TASK_{uuid.uuid4().hex[:8].upper()}"
    state: AgentState = {
        "task_id": t_id,
        "goal": goal,
        "customer_name": None,
        "ticket_id": None,
        "customer": None,
        "ticket": None,
        "payment": None,
        "policy": None,
        "plan": [],
        "current_step": "init",
        "current_step_index": 0,
        "executed_actions": [],
        "observations": [],
        "errors": [],
        "retry_count": 0,
        "max_retries": 1,
        "approval_required": False,
        "approval_id": None,
        "approval_status": None,
        "approval_details": None,
        "verification": {},
        "evidence": {},
        "final_status": "running",
        "summary": "",
        "trace": []
    }
    return state

def run_agent_task(goal: str, task_id: Optional[str] = None) -> AgentState:
    """Run an autonomous agent task from a high-level goal."""
    state = create_initial_state(goal, task_id)
    task_store[state["task_id"]] = state
    
    # Run through LangGraph
    final_state = agent_graph.invoke(state)
    task_store[final_state["task_id"]] = final_state
    return final_state

def resume_task_after_approval(task_id: str, approved: bool, decision_notes: Optional[str] = None) -> AgentState:
    """
    Resume an agent task that was paused at the Human Approval gate.
    Does NOT restart from scratch; preserves full existing state.
    """
    if task_id not in task_store:
        raise ValueError(f"Task '{task_id}' not found in task store")
        
    state = task_store[task_id]
    
    if state["final_status"] != "paused_for_approval":
        return state

    if approved:
        state["approval_status"] = "approved"
        state["final_status"] = "running"
        append_trace(
            state,
            phase="approval",
            action="human_decision",
            status="success",
            decision_source="human approval",
            reasoning="Operations manager explicitly authorized refund disbursement exceeding threshold limit.",
            details=f"Human Manager APPROVED the refund request: {decision_notes or 'Proceed with disbursement'}"
        )
        # Execute remaining steps: execute_action -> verify -> complete
        state = execute_action_node(state)
        state = verify_node(state)
        state = complete_node(state)
    else:
        state["approval_status"] = "rejected"
        state["final_status"] = "rejected_by_human"
        reason = decision_notes or "Rejected by human operations manager."
        append_trace(
            state,
            phase="approval",
            action="human_decision",
            status="failed",
            decision_source="human approval",
            reasoning=f"Operations manager rejected refund disbursement: {reason}",
            details=f"Human Manager REJECTED the refund request: {reason}"
        )
        
        # Update ticket noting rejection
        ticket_id = state["ticket"]["id"]
        tool_registry.execute(
            "update_ticket",
            ticket_id=ticket_id,
            status="closed",
            notes=f"Refund request rejected by manager: {reason}. Ticket closed without disbursement."
        )
        state["ticket"]["status"] = "closed"
        state["summary"] = f"Task halted: Refund request for {state['customer']['name']} was rejected by human manager ({reason}). Ticket {ticket_id} was updated and closed."

    task_store[task_id] = state
    return state
