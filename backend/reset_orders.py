from database import get_db

with get_db() as conn:
    conn.execute("UPDATE orders SET status='delayed',  days_late=4 WHERE id='ORD-1001'")
    conn.execute("UPDATE orders SET status='delivered',days_late=0 WHERE id='ORD-1002'")
    conn.execute("UPDATE orders SET status='processing',days_late=0 WHERE id='ORD-1003'")
    conn.execute("UPDATE orders SET status='shipped',  days_late=0 WHERE id='ORD-1004'")
    conn.execute("UPDATE orders SET status='delayed',  days_late=6 WHERE id='ORD-1005'")
    conn.execute("UPDATE orders SET status='delivered',days_late=0 WHERE id='ORD-1006'")
    conn.execute("UPDATE orders SET status='lost',     days_late=9 WHERE id='ORD-1007'")
    conn.execute("UPDATE orders SET status='refunded', days_late=0 WHERE id='ORD-1008'")
    conn.execute("UPDATE orders SET status='shipped',  days_late=0 WHERE id='ORD-1009'")
    conn.execute("UPDATE orders SET status='processing',days_late=0 WHERE id='ORD-1010'")
    conn.execute("UPDATE orders SET status='delayed',  days_late=5 WHERE id='ORD-1011'")
    conn.execute("UPDATE orders SET status='delivered',days_late=0 WHERE id='ORD-1012'")
    conn.execute("UPDATE orders SET status='shipped',  days_late=0 WHERE id='ORD-1013'")
    conn.execute("UPDATE orders SET status='lost',     days_late=8 WHERE id='ORD-1014'")
    conn.execute("UPDATE orders SET status='processing',days_late=0 WHERE id='ORD-1015'")

    conn.execute("DELETE FROM escalations")

    rows = conn.execute("SELECT id, status FROM orders").fetchall()
    for r in rows:
        print(f"  {r['id']} → {r['status']}")

    print("\n✓ All orders reset to original state")
    print("✓ Escalations cleared")