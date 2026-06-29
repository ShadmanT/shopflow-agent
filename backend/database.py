import sqlite3
import os
import json
from datetime import datetime
from contextlib import contextmanager

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "shopflow.db")

@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()

def create_tables():
    with get_db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS orders (
                id          TEXT PRIMARY KEY,
                customer_name TEXT NOT NULL,
                customer_email TEXT NOT NULL,
                status      TEXT NOT NULL,
                order_total REAL NOT NULL,
                created_at  TEXT NOT NULL,
                estimated_delivery TEXT,
                days_late   INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS order_items (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id    TEXT NOT NULL,
                product_id  TEXT NOT NULL,
                product_name TEXT NOT NULL,
                quantity    INTEGER NOT NULL,
                price       REAL NOT NULL,
                FOREIGN KEY (order_id) REFERENCES orders(id)
            );

            CREATE TABLE IF NOT EXISTS products (
                id          TEXT PRIMARY KEY,
                name        TEXT NOT NULL,
                category    TEXT NOT NULL,
                price       REAL NOT NULL,
                description TEXT,
                colors      TEXT,
                sizes       TEXT,
                rating      REAL,
                review_count INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS product_inventory (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id  TEXT NOT NULL,
                size        TEXT,
                color       TEXT,
                stock       INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY (product_id) REFERENCES products(id)
            );

            CREATE TABLE IF NOT EXISTS escalations (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_id   TEXT UNIQUE NOT NULL,
                order_id    TEXT,
                reason      TEXT NOT NULL,
                urgency     TEXT NOT NULL,
                summary     TEXT,
                status      TEXT DEFAULT 'open',
                created_at  TEXT NOT NULL
            );
        """)



def get_order(order_id: str) -> dict | None:
    with get_db() as conn:
        order = conn.execute(
            "SELECT * FROM orders WHERE id = ?", (order_id,)
        ).fetchone()

        if not order:
            return None

        items = conn.execute(
            "SELECT * FROM order_items WHERE order_id = ?", (order_id,)
        ).fetchall()

        return {
            "order_id":            order["id"],
            "customer_name":       order["customer_name"],
            "customer_email":      order["customer_email"],
            "status":              order["status"],
            "order_total":         order["order_total"],
            "created_at":          order["created_at"],
            "estimated_delivery":  order["estimated_delivery"],
            "days_late":           order["days_late"],
            "refund_eligible":     order["status"] in ("delayed", "lost") or order["days_late"] > 2,
            "items": [
                {
                    "product_id":   row["product_id"],
                    "product_name": row["product_name"],
                    "quantity":     row["quantity"],
                    "price":        row["price"],
                }
                for row in items
            ],
        }


def refund_order(order_id: str, reason: str) -> dict:
    with get_db() as conn:
        order = conn.execute(
            "SELECT * FROM orders WHERE id = ?", (order_id,)
        ).fetchone()

        if not order:
            return {"success": False, "error": "Order not found", "order_id": order_id}

        eligible = order["status"] in ("delayed", "lost") or order["days_late"] > 2
        if not eligible:
            return {"success": False, "error": f"Order not eligible for refund (status: {order['status']})", "order_id": order_id}

        if order["status"] == "refunded":
            return {"success": False, "error": "Order has already been refunded", "order_id": order_id}

        refund_id = f"REF-{datetime.now().strftime('%Y%m%d')}-{order_id.split('-')[1]}"

        conn.execute(
            "UPDATE orders SET status = 'refunded' WHERE id = ?", (order_id,)
        )

        return {
            "success":              True,
            "refund_id":            refund_id,
            "order_id":             order_id,
            "amount":               order["order_total"],
            "reason":               reason,
            "processed_at":         datetime.now().isoformat(),
            "message":              "Refund will appear in 3-5 business days",
        }


def get_product(product_id: str = None, product_name: str = None) -> dict | None:
    with get_db() as conn:
        if product_id:
            row = conn.execute(
                "SELECT * FROM products WHERE id = ?", (product_id,)
            ).fetchone()
        elif product_name:
            words = product_name.strip().split()
            query = "SELECT * FROM products WHERE " + " AND ".join(
                ["LOWER(name) LIKE ?" for _ in words]
            )
            params = [f"%{w.lower()}%" for w in words]
            row = conn.execute(query, params).fetchone()
        else:
            return None

        if not row:
            return None

        return {
            "product_id":    row["id"],
            "name":          row["name"],
            "category":      row["category"],
            "price":         row["price"],
            "description":   row["description"],
            "colors":        row["colors"].split(",") if row["colors"] else [],
            "sizes":         row["sizes"].split(",") if row["sizes"] else [],
            "rating":        row["rating"],
            "review_count":  row["review_count"],
        }


def get_inventory(product_id: str = None, product_name: str = None) -> dict | None:
    with get_db() as conn:
        if not product_id and product_name:
            words = product_name.strip().split()
            query = "SELECT id FROM products WHERE " + " AND ".join(
                ["LOWER(name) LIKE ?" for _ in words]
            )
            params = [f"%{w.lower()}%" for w in words]
            row = conn.execute(query, params).fetchone()
            if not row:
                return None
            product_id = row["id"]

        product = conn.execute(
            "SELECT * FROM products WHERE id = ?", (product_id,)
        ).fetchone()

        if not product:
            return None

        variants = conn.execute(
            "SELECT size, color, stock FROM product_inventory WHERE product_id = ?",
            (product_id,)
        ).fetchall()

        total_stock = sum(v["stock"] for v in variants)

        restock_date = "2026-06-01" if total_stock == 0 else None

        return {
            "product_id":    product["id"],
            "product_name":  product["name"],
            "total_stock":   total_stock,
            "variants": [
                {"size": v["size"], "color": v["color"], "stock": v["stock"]}
                for v in variants
            ],
            "restock_date":  restock_date,
        }


def create_escalation(order_id: str | None, reason: str, urgency: str, summary: str = None) -> dict:
    with get_db() as conn:
        ticket_id = f"TKT-{datetime.now().strftime('%Y%m%d%H%M%S')}"

        response_times = {"low": "24 hours", "medium": "4 hours", "high": "1 hour"}

        conn.execute("""
            INSERT INTO escalations (ticket_id, order_id, reason, urgency, summary, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (ticket_id, order_id, reason, urgency, summary, datetime.now().isoformat()))

        return {
            "ticket_id":               ticket_id,
            "urgency":                 urgency,
            "reason":                  reason,
            "estimated_response_time": response_times.get(urgency, "4 hours"),
            "message":                 "A human agent will follow up via the customer's email on file",
        }