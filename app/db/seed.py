import datetime
from app.db.database import get_connection, init_db

def seed_database(db_path: str = None) -> None:
    init_db(db_path)
    conn = get_connection(db_path)
    cursor = conn.cursor()

    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    yesterday = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=1)).isoformat()

    # Clear existing data for fresh idempotency
    cursor.execute("DELETE FROM approvals;")
    cursor.execute("DELETE FROM refunds;")
    cursor.execute("DELETE FROM tickets;")
    cursor.execute("DELETE FROM payments;")
    cursor.execute("DELETE FROM customers;")
    cursor.execute("DELETE FROM transient_failures;")

    # 1. Customers
    customers = [
        ("CUST001", "Rahul Sharma", "rahul@example.test", "+91 98765 43210", "standard", yesterday),
        ("CUST002", "Priya Patel", "priya@example.test", "+91 98765 43211", "pro", yesterday),
        ("CUST003", "Amit Kumar", "amit@example.test", "+91 98765 43212", "enterprise", yesterday),
        ("CUST004", "Neha Verma", "neha@example.test", "+91 98765 43213", "standard", yesterday),
        ("CUST005", "Vikram Singh", "vikram@example.test", "+91 98765 43214", "pro", yesterday),
        ("CUST006", "Ananya Rao", "ananya@example.test", "+91 98765 43215", "standard", yesterday),
    ]
    cursor.executemany(
        "INSERT INTO customers (id, name, email, phone, tier, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        customers
    )

    # 2. Payments
    payments = [
        # SCENARIO 1: Rahul Sharma - <= 5000, charged, no refund yet
        ("PAY9001", "CUST001", 2499.0, "INR", "charged", "none", None, None, yesterday, yesterday),
        # SCENARIO 2: Priya Patel - <= 5000, charged, transient failure on 1st refund call
        ("PAY9002", "CUST002", 3200.0, "INR", "charged", "none", None, None, yesterday, yesterday),
        # SCENARIO 3: Amit Kumar - > 5000 (8500), charged, requires human approval
        ("PAY9012", "CUST003", 8500.0, "INR", "charged", "none", None, None, yesterday, yesterday),
        # SCENARIO 4: Neha Verma - already refunded, prevent duplicate
        ("PAY9025", "CUST004", 1999.0, "INR", "charged", "completed", "REF7701", "Customer disputed double debit", yesterday, yesterday),
        # SCENARIO 5: Vikram Singh - payment failed, cannot refund
        ("PAY9033", "CUST005", 4500.0, "INR", "failed", "none", None, None, yesterday, yesterday),
    ]
    cursor.executemany(
        """INSERT INTO payments 
        (id, customer_id, amount, currency, status, refund_status, refund_id, refund_reason, created_at, updated_at) 
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        payments
    )

    # 3. Existing Refunds (for Scenario 4)
    cursor.execute(
        """INSERT INTO refunds (id, payment_id, customer_id, amount, status, reason, created_at) 
        VALUES ('REF7701', 'PAY9025', 'CUST004', 1999.0, 'completed', 'Customer disputed double debit', ?)""",
        (yesterday,)
    )

    # 4. Support Tickets
    tickets = [
        ("TICKET1024", "CUST001", "Payment charged but subscription inactive", "PAY9001", "open", "", yesterday, yesterday),
        ("TICKET1025", "CUST002", "Charged twice for annual pro pass", "PAY9002", "open", "", yesterday, yesterday),
        ("TICKET1030", "CUST003", "Enterprise seat renewal billed incorrectly", "PAY9012", "open", "", yesterday, yesterday),
        ("TICKET1042", "CUST004", "Payment charged twice, first refund processed earlier", "PAY9025", "open", "", yesterday, yesterday),
        ("TICKET1050", "CUST005", "Bank deducted funds but gateway marked transaction failed", "PAY9033", "open", "", yesterday, yesterday),
        ("TICKET1060", "CUST006", "Refund requested for missing order with non-existent payment", "PAY9999", "open", "", yesterday, yesterday),
    ]
    cursor.executemany(
        """INSERT INTO tickets 
        (id, customer_id, issue, payment_id, status, notes, created_at, updated_at) 
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        tickets
    )

    # 5. Transient failure configuration: PAY9002 will fail on 1st attempt, then succeed
    cursor.execute(
        "INSERT INTO transient_failures (payment_id, failures_remaining) VALUES ('PAY9002', 1)"
    )

    conn.commit()
    conn.close()
    print("Database seeded successfully with all 5 core scenarios and 6 enterprise test cases.")

if __name__ == "__main__":
    seed_database()
