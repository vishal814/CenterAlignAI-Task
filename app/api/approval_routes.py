import datetime
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from app.db.database import get_connection

router = APIRouter(prefix="/api/approvals", tags=["Human Approvals"])

class ApprovalDecision(BaseModel):
    notes: Optional[str] = "Approved by manager"

class ApprovalReject(BaseModel):
    reason: Optional[str] = "Rejected by manager: Insufficient justification"

@router.get("")
def list_approvals(status: Optional[str] = None):
    conn = get_connection()
    if status:
        rows = conn.execute("SELECT * FROM approvals WHERE status = ? ORDER BY created_at DESC", (status,)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM approvals ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]

@router.get("/{approval_id}")
def get_approval(approval_id: str):
    conn = get_connection()
    row = conn.execute("SELECT * FROM approvals WHERE id = ?", (approval_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Approval request not found")
    return dict(row)

@router.post("/{approval_id}/approve")
def approve_request(approval_id: str, decision: ApprovalDecision):
    conn = get_connection()
    row = conn.execute("SELECT * FROM approvals WHERE id = ?", (approval_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Approval request not found")
    
    app_data = dict(row)
    if app_data["status"] != "pending":
        conn.close()
        return {"success": False, "message": f"Approval is already '{app_data['status']}'"}
    
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    conn.execute(
        "UPDATE approvals SET status = 'approved', decision_notes = ?, resolved_at = ? WHERE id = ?",
        (decision.notes, now, approval_id)
    )
    conn.commit()
    conn.close()
    return {"success": True, "approvalId": approval_id, "status": "approved", "notes": decision.notes}

@router.post("/{approval_id}/reject")
def reject_request(approval_id: str, decision: ApprovalReject):
    conn = get_connection()
    row = conn.execute("SELECT * FROM approvals WHERE id = ?", (approval_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Approval request not found")
    
    app_data = dict(row)
    if app_data["status"] != "pending":
        conn.close()
        return {"success": False, "message": f"Approval is already '{app_data['status']}'"}
    
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    conn.execute(
        "UPDATE approvals SET status = 'rejected', decision_notes = ?, resolved_at = ? WHERE id = ?",
        (decision.reason, now, approval_id)
    )
    conn.commit()
    conn.close()
    return {"success": True, "approvalId": approval_id, "status": "rejected", "reason": decision.reason}
