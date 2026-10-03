from typing import Dict, Any, List
from app.db.database import get_connection

def search_customers(query: str) -> Dict[str, Any]:
    """Search customers by name, email, or ID."""
    conn = get_connection()
    pattern = f"%{query.strip()}%"
    rows = conn.execute(
        "SELECT * FROM customers WHERE id LIKE ? OR name LIKE ? OR email LIKE ?",
        (pattern, pattern, pattern)
    ).fetchall()
    conn.close()
    
    results = [dict(r) for r in rows]
    return {
        "success": True,
        "query": query,
        "count": len(results),
        "customers": results
    }

def get_customer(customer_id: str) -> Dict[str, Any]:
    """Get full details of a specific customer by ID."""
    conn = get_connection()
    row = conn.execute("SELECT * FROM customers WHERE id = ?", (customer_id.strip(),)).fetchone()
    conn.close()
    
    if not row:
        return {
            "success": False,
            "error": f"Customer '{customer_id}' not found",
            "customer": None
        }
    return {
        "success": True,
        "customer": dict(row)
    }
