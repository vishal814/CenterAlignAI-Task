import datetime
from typing import Dict, Any, Optional
from app.db.database import get_connection

def search_tickets(customer_id: Optional[str] = None, query: Optional[str] = None) -> Dict[str, Any]:
    """Search for support tickets by customer ID or issue keywords."""
    conn = get_connection()
    sql = "SELECT * FROM tickets WHERE 1=1"
    params = []
    if customer_id:
        sql += " AND customer_id = ?"
        params.append(customer_id.strip())
    if query:
        pattern = f"%{query.strip()}%"
        sql += " AND (issue LIKE ? OR notes LIKE ? OR id LIKE ?)"
        params.extend([pattern, pattern, pattern])
        
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    
    results = [dict(r) for r in rows]
    return {
        "success": True,
        "count": len(results),
        "tickets": results
    }

def get_ticket(ticket_id: str) -> Dict[str, Any]:
    """Get full details of a support ticket by ticket ID."""
    conn = get_connection()
    row = conn.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id.strip(),)).fetchone()
    conn.close()
    
    if not row:
        return {
            "success": False,
            "error": f"Ticket '{ticket_id}' not found",
            "ticket": None
        }
    return {
        "success": True,
        "ticket": dict(row)
    }

def update_ticket(ticket_id: str, status: str, notes: Optional[str] = "") -> Dict[str, Any]:
    """Update support ticket status and append investigation/resolution notes."""
    conn = get_connection()
    row = conn.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id.strip(),)).fetchone()
    if not row:
        conn.close()
        return {
            "success": False,
            "error": f"Ticket '{ticket_id}' not found"
        }
        
    current = dict(row)
    existing_notes = current.get("notes") or ""
    new_notes = f"{existing_notes}\n[AI Operator]: {notes}".strip() if notes else existing_notes
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    
    conn.execute(
        "UPDATE tickets SET status = ?, notes = ?, updated_at = ? WHERE id = ?",
        (status, new_notes, now, ticket_id.strip())
    )
    conn.commit()
    
    updated_row = conn.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id.strip(),)).fetchone()
    conn.close()
    
    return {
        "success": True,
        "ticketId": ticket_id,
        "status": status,
        "notes": new_notes,
        "updatedAt": now
    }

def verify_ticket(ticket_id: str, expected_status: str) -> Dict[str, Any]:
    """
    Independently verify that the ticket status in SQLite matches the expected final state.
    """
    conn = get_connection()
    row = conn.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id.strip(),)).fetchone()
    conn.close()
    
    if not row:
        return {
            "success": False,
            "verified": False,
            "error": f"Verification failed: Ticket '{ticket_id}' does not exist in database",
            "ticketId": ticket_id
        }
        
    ticket = dict(row)
    current_status = ticket["status"]
    is_verified = (current_status.lower() == expected_status.lower())
    
    return {
        "success": True,
        "verified": is_verified,
        "ticketId": ticket_id,
        "currentStatus": current_status,
        "expectedStatus": expected_status,
        "notes": ticket["notes"],
        "updatedAt": ticket["updated_at"],
        "message": f"Ticket status is '{current_status}' (expected '{expected_status}')" if is_verified else f"Verification MISMATCH: Current status is '{current_status}', expected '{expected_status}'"
    }
