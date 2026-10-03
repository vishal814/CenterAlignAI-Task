import uuid
import datetime
from pathlib import Path
from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from app.db.database import get_connection
from app.db.seed import seed_database
from app.models.customer import Customer
from app.models.ticket import SupportTicket, TicketUpdate
from app.models.payment import Payment, RefundRequest, RefundRecord
from app.config import settings

router = APIRouter(prefix="/api", tags=["Enterprise Mock API"])

# ==========================================
# CUSTOMER ENDPOINTS
# ==========================================

@router.get("/customers", response_model=List[Customer])
def list_customers():
    conn = get_connection()
    rows = conn.execute("SELECT * FROM customers ORDER BY id ASC").fetchall()
    conn.close()
    return [Customer(**dict(row)) for row in rows]

@router.get("/customers/{customer_id}", response_model=Customer)
def get_customer(customer_id: str):
    conn = get_connection()
    row = conn.execute("SELECT * FROM customers WHERE id = ? OR name LIKE ?", (customer_id, f"%{customer_id}%")).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail=f"Customer '{customer_id}' not found")
    return Customer(**dict(row))

# ==========================================
# TICKET ENDPOINTS
# ==========================================

@router.get("/tickets", response_model=List[SupportTicket])
def list_tickets(customer_id: Optional[str] = Query(None)):
    conn = get_connection()
    if customer_id:
        rows = conn.execute("SELECT * FROM tickets WHERE customer_id = ? ORDER BY id ASC", (customer_id,)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM tickets ORDER BY id ASC").fetchall()
    conn.close()
    return [SupportTicket(**dict(row)) for row in rows]

@router.get("/tickets/search", response_model=List[SupportTicket])
def search_tickets(
    query: Optional[str] = Query(None),
    customer_id: Optional[str] = Query(None)
):
    conn = get_connection()
    sql = "SELECT * FROM tickets WHERE 1=1"
    params = []
    if customer_id:
        sql += " AND customer_id = ?"
        params.append(customer_id)
    if query:
        sql += " AND (issue LIKE ? OR notes LIKE ? OR id LIKE ?)"
        pattern = f"%{query}%"
        params.extend([pattern, pattern, pattern])
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [SupportTicket(**dict(row)) for row in rows]

@router.get("/tickets/{ticket_id}", response_model=SupportTicket)
def get_ticket(ticket_id: str):
    conn = get_connection()
    row = conn.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail=f"Ticket '{ticket_id}' not found")
    return SupportTicket(**dict(row))

@router.patch("/tickets/{ticket_id}", response_model=SupportTicket)
def update_ticket(ticket_id: str, update: TicketUpdate):
    conn = get_connection()
    row = conn.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail=f"Ticket '{ticket_id}' not found")
    
    current = dict(row)
    new_status = update.status if update.status is not None else current["status"]
    
    # Append or replace notes
    if update.notes is not None:
        if current["notes"]:
            new_notes = f"{current['notes']}\n{update.notes}".strip()
        else:
            new_notes = update.notes.strip()
    else:
        new_notes = current["notes"]
        
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    conn.execute(
        "UPDATE tickets SET status = ?, notes = ?, updated_at = ? WHERE id = ?",
        (new_status, new_notes, now, ticket_id)
    )
    conn.commit()
    updated = conn.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
    conn.close()
    return SupportTicket(**dict(updated))

# ==========================================
# PAYMENT & REFUND ENDPOINTS
# ==========================================

@router.get("/payments/{payment_id}", response_model=Payment)
def get_payment(payment_id: str):
    conn = get_connection()
    row = conn.execute("SELECT * FROM payments WHERE id = ?", (payment_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail=f"Payment '{payment_id}' not found")
    return Payment(**dict(row))

@router.get("/payments/{payment_id}/refund-status")
def get_payment_refund_status(payment_id: str):
    conn = get_connection()
    row = conn.execute("SELECT * FROM payments WHERE id = ?", (payment_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail=f"Payment '{payment_id}' not found")
    
    payment = dict(row)
    refund = None
    if payment["refund_id"]:
        refund_row = conn.execute("SELECT * FROM refunds WHERE id = ?", (payment["refund_id"],)).fetchone()
        if refund_row:
            refund = dict(refund_row)
            
    conn.close()
    return {
        "paymentId": payment["id"],
        "paymentStatus": payment["status"],
        "amount": payment["amount"],
        "currency": payment["currency"],
        "refundStatus": payment["refund_status"],
        "refundId": payment["refund_id"],
        "refund": refund
    }

@router.post("/payments/{payment_id}/refund")
def process_refund(payment_id: str, request: RefundRequest):
    conn = get_connection()
    # 1. Check transient failure simulator
    transient = conn.execute(
        "SELECT failures_remaining FROM transient_failures WHERE payment_id = ?",
        (payment_id,)
    ).fetchone()
    
    if transient and transient["failures_remaining"] > 0:
        # Decrement transient failure count so next attempt succeeds!
        conn.execute(
            "UPDATE transient_failures SET failures_remaining = failures_remaining - 1 WHERE payment_id = ?",
            (payment_id,)
        )
        conn.commit()
        conn.close()
        return {
            "success": False,
            "error": "temporary_payment_service_error",
            "retryable": True,
            "message": "Payment gateway timed out or returned a transient 503 error. Retry is recommended."
        }

    # 2. Fetch payment
    row = conn.execute("SELECT * FROM payments WHERE id = ?", (payment_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail=f"Payment '{payment_id}' not found")
    
    payment = dict(row)
    
    # 3. Validation: Payment status must be 'charged'
    if payment["status"] != "charged":
        conn.close()
        return {
            "success": False,
            "error": f"Cannot refund payment with status '{payment['status']}' (must be 'charged')",
            "retryable": False
        }
    
    # 4. Validation: Duplicate refund prevention
    if payment["refund_status"] == "completed":
        conn.close()
        return {
            "success": False,
            "error": "duplicate_refund_prevented",
            "retryable": False,
            "message": f"Payment {payment_id} was already refunded under Refund ID {payment['refund_id']}",
            "existingRefundId": payment["refund_id"]
        }

    refund_amount = request.amount if request.amount is not None else payment["amount"]
    refund_id = f"REF{uuid.uuid4().hex[:6].upper()}"
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()

    # Record in refunds table
    conn.execute(
        "INSERT INTO refunds (id, payment_id, customer_id, amount, status, reason, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (refund_id, payment_id, payment["customer_id"], refund_amount, "completed", request.reason, now)
    )

    # Update payments table
    conn.execute(
        "UPDATE payments SET refund_status = 'completed', refund_id = ?, refund_reason = ?, updated_at = ? WHERE id = ?",
        (refund_id, request.reason, now, payment_id)
    )

    conn.commit()
    conn.close()

    return {
        "success": True,
        "refundId": refund_id,
        "paymentId": payment_id,
        "amount": refund_amount,
        "currency": payment["currency"],
        "status": "completed",
        "message": f"Refund of ₹{refund_amount} successfully processed for payment {payment_id}"
    }

# ==========================================
# POLICIES & UTILITY ENDPOINTS
# ==========================================

@router.get("/policies/refund-policy")
def get_refund_policy():
    policy_path = Path(settings.POLICY_FILE_PATH)
    if not policy_path.exists():
        raise HTTPException(status_code=404, detail="Refund policy file not found")
    content = policy_path.read_text(encoding="utf-8")
    return {
        "policyName": "refund_policy.md",
        "content": content,
        "autoRefundThreshold": settings.AUTO_REFUND_THRESHOLD
    }

@router.post("/db/reset")
def reset_database():
    seed_database()
    return {"status": "success", "message": "Database reset to initial mock state successfully"}
