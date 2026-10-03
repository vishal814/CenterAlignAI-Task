from typing import TypedDict, List, Dict, Any, Optional

class TraceStep(TypedDict):
    step_id: int
    timestamp: str
    phase: str          # e.g., "understand", "plan", "execute", "observe", "adapt", "approval", "verify", "complete"
    action: str         # Tool name or action label
    status: str         # "pending", "running", "success", "failed", "retried", "paused", "skipped"
    decision_source: str # "LLM decision", "deterministic safety rule", "human approval", "recovery logic"
    reasoning: Optional[str] # Explicit rationale
    input_data: Optional[Dict[str, Any]]
    output_data: Optional[Dict[str, Any]]
    details: str

class AgentState(TypedDict):
    task_id: str
    goal: str
    customer_name: Optional[str]
    ticket_id: Optional[str]
    
    # Context entities
    customer: Optional[Dict[str, Any]]
    ticket: Optional[Dict[str, Any]]
    payment: Optional[Dict[str, Any]]
    policy: Optional[Dict[str, Any]]
    
    # Planning & Execution State
    plan: List[Dict[str, Any]]
    current_step: str
    current_step_index: int
    executed_actions: List[Dict[str, Any]]
    observations: List[Dict[str, Any]]
    errors: List[Dict[str, Any]]
    
    # Resilience & Recovery
    retry_count: int
    max_retries: int
    
    # Human Approval Gate
    approval_required: bool
    approval_id: Optional[str]
    approval_status: Optional[str]  # None, "pending", "approved", "rejected"
    approval_details: Optional[Dict[str, Any]]
    
    # Independent Verification
    verification: Dict[str, Any]
    
    # Completion & Artifacts
    evidence: Dict[str, Any]
    final_status: str               # "initializing", "running", "paused_for_approval", "completed", "failed", "rejected_by_human"
    summary: str
    trace: List[Dict[str, Any]]
