import uuid
import datetime
from typing import Dict, Any, Optional
from app.db.database import get_connection

def get_payment(payment_id: str) -> Dict[str, Any]:
    """Retrieve full payment details by payment ID."""
    conn = get_connection()
    row = conn.execute("SELECT * FROM payments WHERE id = ?", (payment_id.strip(),)).fetchone()
    conn.close()
    
    if not row:
        return {
            "success": False,
            "error": f"Payment '{payment_id}' not found",
            "payment": None
        }
    return {
        "success": True,
        "payment": dict(row)
    }

def issue_refund(payment_id: str, reason: str, amount: Optional[float] = None) -> Dict[str, Any]:
    """
    Execute a refund against the payment gateway.
    Handles transient gateway errors with retryable flags, and enforces duplicate prevention.
    """
    conn = get_connection()
    pid = payment_id.strip()

    # 1. Check transient failure simulator
    transient = conn.execute(
        "SELECT failures_remaining FROM transient_failures WHERE payment_id = ?",
        (pid,)
    ).fetchone()

    if transient and transient["failures_remaining"] > 0:
        # Decrement transient failure count so next retry succeeds
        conn.execute(
            "UPDATE transient_failures SET failures_remaining = failures_remaining - 1 WHERE payment_id = ?",
            (pid,)
        )
        conn.commit()
        conn.close()
        return {
            "success": False,
            "error": "temporary_payment_service_error",
            "retryable": True,
            "message": "Payment gateway timed out or returned transient 503 error. Retry is recommended."
        }

    # 2. Fetch payment record
    row = conn.execute("SELECT * FROM payments WHERE id = ?", (pid,)).fetchone()
    if not row:
        conn.close()
        return {
            "success": False,
            "error": f"Payment '{pid}' not found in database",
            "retryable": False
        }

    payment = dict(row)

    # 3. Check payment status
    if payment["status"] != "charged":
        conn.close()
        return {
            "success": False,
            "error": f"Invalid payment status '{payment['status']}' - only charged payments can be refunded",
            "retryable": False
        }

    # 4. Check duplicate refund prevention
    if payment["refund_status"] == "completed":
        conn.close()
        return {
            "success": False,
            "error": "duplicate_refund_prevented",
            "retryable": False,
            "message": f"Payment {pid} was already refunded under Refund ID {payment['refund_id']}",
            "existingRefundId": payment["refund_id"]
        }

    refund_amount = amount if amount is not None else payment["amount"]
    refund_id = f"REF{uuid.uuid4().hex[:6].upper()}"
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()

    # Insert into refunds table
    conn.execute(
        "INSERT INTO refunds (id, payment_id, customer_id, amount, status, reason, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (refund_id, pid, payment["customer_id"], refund_amount, "completed", reason, now)
    )

    # Update payment record
    conn.execute(
        "UPDATE payments SET refund_status = 'completed', refund_id = ?, refund_reason = ?, updated_at = ? WHERE id = ?",
        (refund_id, reason, now, pid)
    )

    conn.commit()
    conn.close()

    return {
        "success": True,
        "refundId": refund_id,
        "paymentId": pid,
        "customerId": payment["customer_id"],
        "amount": refund_amount,
        "currency": payment["currency"],
        "status": "completed",
        "message": f"Successfully refunded ₹{refund_amount} for payment {pid}"
    }

def verify_refund(payment_id: str, expected_refund_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Independently verify that the refund actually exists in the database ledger
    and that the payment state reflects 'completed' refund status.
    """
    conn = get_connection()
    pid = payment_id.strip()
    
    pay_row = conn.execute("SELECT * FROM payments WHERE id = ?", (pid,)).fetchone()
    if not pay_row:
        conn.close()
        return {
            "success": False,
            "verified": False,
            "error": f"Verification failed: Payment '{pid}' does not exist in ledger",
            "paymentId": pid
        }

    payment = dict(pay_row)
    refund_row = None
    if payment["refund_id"]:
        refund_row = conn.execute("SELECT * FROM refunds WHERE id = ?", (payment["refund_id"],)).fetchone()
    conn.close()

    if not payment["refund_id"] or not refund_row:
        return {
            "success": True,
            "verified": False,
            "paymentId": pid,
            "refundStatus": payment["refund_status"],
            "message": f"Verification failed: Payment {pid} has no associated completed refund record in database"
        }

    refund = dict(refund_row)
    id_matches = True
    if expected_refund_id and refund["id"] != expected_refund_id:
        id_matches = False

    is_verified = (payment["refund_status"] == "completed" and refund["status"] == "completed" and id_matches)

    return {
        "success": True,
        "verified": is_verified,
        "paymentId": pid,
        "refundId": refund["id"],
        "refundAmount": refund["amount"],
        "refundReason": refund["reason"],
        "refundCreatedAt": refund["created_at"],
        "paymentRefundStatus": payment["refund_status"],
        "message": "Refund independently verified in database ledger" if is_verified else "Verification failed: Refund status mismatch"
    }
