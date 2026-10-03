from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from app.agent.graph import run_agent_task, resume_task_after_approval, task_store
from app.db.database import get_connection

router = APIRouter(prefix="/api/tasks", tags=["Agent Tasks"])

class CreateTaskRequest(BaseModel):
    goal: str = Field(..., description="High-level company goal or request")

class ApprovalActionRequest(BaseModel):
    decision_notes: Optional[str] = "Approved by human operator"

@router.post("")
def start_task(req: CreateTaskRequest):
    """
    Initiate an autonomous agent execution from a high-level goal.
    """
    if not req.goal or not req.goal.strip():
        raise HTTPException(status_code=400, detail="Goal cannot be empty")
    
    state = run_agent_task(req.goal.strip())
    return {
        "taskId": state["task_id"],
        "goal": state["goal"],
        "status": state["final_status"],
        "approvalRequired": state["approval_required"],
        "approvalId": state["approval_id"],
        "summary": state["summary"],
        "state": state
    }

@router.get("")
def list_tasks():
    """List all agent tasks in memory."""
    tasks = []
    for tid, st in reversed(list(task_store.items())):
        tasks.append({
            "taskId": tid,
            "goal": st["goal"],
            "status": st["final_status"],
            "approvalRequired": st["approval_required"],
            "approvalStatus": st.get("approval_status"),
            "customer": st.get("customer"),
            "summary": st.get("summary")
        })
    return tasks

@router.get("/{task_id}")
def get_task(task_id: str):
    """Fetch complete agent state, execution trace, plan, and evidence for a task."""
    if task_id not in task_store:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")
    return task_store[task_id]

@router.post("/{task_id}/approve")
def approve_task(task_id: str, req: ApprovalActionRequest):
    """Approve a paused agent task and resume autonomous execution."""
    if task_id not in task_store:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")
    
    # Also update DB approvals table if approval_id exists
    st = task_store[task_id]
    if st.get("approval_id"):
        conn = get_connection()
        conn.execute(
            "UPDATE approvals SET status = 'approved', decision_notes = ? WHERE id = ?",
            (req.decision_notes, st["approval_id"])
        )
        conn.commit()
        conn.close()

    resumed_state = resume_task_after_approval(task_id, approved=True, decision_notes=req.decision_notes)
    return {
        "taskId": task_id,
        "status": resumed_state["final_status"],
        "summary": resumed_state["summary"],
        "state": resumed_state
    }

@router.post("/{task_id}/reject")
def reject_task(task_id: str, req: ApprovalActionRequest):
    """Reject a paused agent task and trigger safe closure."""
    if task_id not in task_store:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")
    
    # Also update DB approvals table if approval_id exists
    st = task_store[task_id]
    if st.get("approval_id"):
        conn = get_connection()
        conn.execute(
            "UPDATE approvals SET status = 'rejected', decision_notes = ? WHERE id = ?",
            (req.decision_notes, st["approval_id"])
        )
        conn.commit()
        conn.close()

    resumed_state = resume_task_after_approval(task_id, approved=False, decision_notes=req.decision_notes)
    return {
        "taskId": task_id,
        "status": resumed_state["final_status"],
        "summary": resumed_state["summary"],
        "state": resumed_state
    }
