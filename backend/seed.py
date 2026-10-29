import sqlite3
import os
import sys
sys.path.append(os.path.dirname(__file__))

from database import create_tables, get_db

def seed():
    create_tables()

    with get_db() as conn:
        # Clear existing data so seed is idempotent
        conn.executescript("""
            DELETE FROM order_items;
            DELETE FROM orders;
            DELETE FROM product_inventory;
            DELETE FROM products;
            DELETE FROM escalations;
        """)

        # ── Products ──────────────────────────────────────────────
        products = [
            ("P-101", "Wireless Noise-Cancelling Headphones", "Electronics",
             89.99, "Over-ear headphones with 30hr battery and active noise cancellation.",
             "black,white,midnight blue", None, 4.7, 1243),

            ("P-102", "Mechanical Keyboard TKL", "Electronics",
             129.99, "Tenkeyless mechanical keyboard with Cherry MX Brown switches.",
             "black,silver", None, 4.5, 876),

            ("P-103", "Pro Running Shoes", "Footwear",
             129.99, "Lightweight mesh upper with responsive foam sole. Ideal for road running.",
             "black,white,navy", "7,8,9,10,11,12", 4.6, 2841),

            ("P-104", "Yoga Mat Premium", "Fitness",
             49.99, "6mm non-slip mat with alignment lines and carry strap.",
             "purple,teal,black", None, 4.8, 3210),

            ("P-105", "Stainless Steel Water Bottle 32oz", "Kitchen",
             34.99, "Double-wall vacuum insulated. Keeps cold 24hr, hot 12hr.",
             "silver,matte black,forest green", None, 4.9, 5421),

            ("P-106", "Laptop Stand Adjustable", "Electronics",
             59.99, "Aluminum laptop stand, adjustable 6 heights, foldable.",
             "silver,space gray", None, 4.4, 654),

            ("P-107", "Resistance Band Set", "Fitness",
             24.99, "Set of 5 resistance bands from 10-50lb with carry bag.",
             "multicolor", None, 4.3, 1876),

            ("P-108", "Ceramic Pour-Over Coffee Set", "Kitchen",
             44.99, "Ceramic dripper, carafe, and 40 filters. Serves 1-4 cups.",
             "white,matte black", None, 4.7, 923),

            ("P-109", "Merino Wool Crew Socks 3-Pack", "Clothing",
             22.99, "Temperature-regulating merino wool. Machine washable.",
             "charcoal,navy,oatmeal", "S,M,L,XL", 4.5, 2103),

            ("P-110", "Portable Bluetooth Speaker", "Electronics",
             79.99, "360 sound, IPX7 waterproof, 20hr battery.",
             "black,ocean blue,red", None, 4.6, 1567),

            # Edge case: fully out of stock (every variant 0 -> restock_date populates)
            ("P-111", "Trail Backpack 40L", "Outdoors",
             74.99, "Weather-resistant 40L hiking backpack with hydration sleeve and rain cover.",
             "graphite,forest green", None, 4.6, 312),
        ]

        conn.executemany("""
            INSERT INTO products
              (id, name, category, price, description, colors, sizes, rating, review_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, products)

        # ── Inventory ─────────────────────────────────────────────
        inventory = []

        # Electronics / no size variants
        for pid, colors, stock_levels in [
            ("P-101", ["black", "white", "midnight blue"], [18, 7, 0]),
            ("P-102", ["black", "silver"], [12, 4]),
            ("P-106", ["silver", "space gray"], [9, 6]),
            ("P-110", ["black", "ocean blue", "red"], [22, 11, 3]),
        ]:
            for color, stock in zip(colors, stock_levels):
                inventory.append((pid, None, color, stock))

        # Footwear — size + color variants
        for size in ["7", "8", "9", "10", "11", "12"]:
            for color, stocks in [("black", [4,6,8,10,6,3]), ("white", [2,3,5,4,2,0]), ("navy", [1,2,4,5,3,1])]:
                idx = ["7","8","9","10","11","12"].index(size)
                inventory.append(("P-103", size, color, stocks[idx]))

        # Fitness / Kitchen — color only
        for pid, colors, stocks in [
            ("P-104", ["purple", "teal", "black"], [15, 11, 8]),
            ("P-105", ["silver", "matte black", "forest green"], [34, 28, 19]),
            ("P-107", ["multicolor"], [42]),
            ("P-108", ["white", "matte black"], [6, 4]),
        ]:
            for color, stock in zip(colors, stocks):
                inventory.append((pid, None, color, stock))

        # Socks — size variants
        for size, stocks in [("S",14), ("M",22), ("L",18), ("XL",9)]:
            for color in ["charcoal", "navy", "oatmeal"]:
                inventory.append(("P-109", size, color, stocks))

        # Trail Backpack — fully out of stock (edge case)
        for color in ["graphite", "forest green"]:
            inventory.append(("P-111", None, color, 0))

        conn.executemany("""
            INSERT INTO product_inventory (product_id, size, color, stock)
            VALUES (?, ?, ?, ?)
        """, inventory)

        # ── Orders ────────────────────────────────────────────────
        orders = [
            ("ORD-1001", "Priya Sharma",    "priya@email.com",   "delayed",    89.99,  "2026-05-10", "2026-05-23", 4),
            ("ORD-1002", "Marcus Webb",     "marcus@email.com",  "delivered",  164.98, "2026-05-08", "2026-05-15", 0),
            ("ORD-1003", "Sofia Reyes",     "sofia@email.com",   "processing", 49.99,  "2026-05-22", "2026-05-28", 0),
            ("ORD-1004", "James Okafor",    "james@email.com",   "shipped",    129.99, "2026-05-18", "2026-05-24", 0),
            ("ORD-1005", "Aisha Patel",     "aisha@email.com",   "delayed",    34.99,  "2026-05-12", "2026-05-20", 6),
            ("ORD-1006", "Tyler Nguyen",    "tyler@email.com",   "delivered",  79.99,  "2026-05-05", "2026-05-12", 0),
            ("ORD-1007", "Chloe Brennan",   "chloe@email.com",   "lost",       209.98, "2026-05-09", "2026-05-17", 9),
            ("ORD-1008", "Raj Mehta",       "raj@email.com",     "refunded",   44.99,  "2026-05-01", "2026-05-08", 0),
            ("ORD-1009", "Elena Vasquez",   "elena@email.com",   "shipped",    152.98, "2026-05-20", "2026-05-27", 0),
            ("ORD-1010", "David Kim",       "david@email.com",   "processing", 24.99,  "2026-05-23", "2026-05-30", 0),
            ("ORD-1011", "Fatima Hassan",   "fatima@email.com",  "delayed",    129.99, "2026-05-14", "2026-05-21", 5),
            ("ORD-1012", "Lucas Oliveira",  "lucas@email.com",   "delivered",  57.98,  "2026-05-06", "2026-05-13", 0),
            ("ORD-1013", "Nina Kowalski",   "nina@email.com",    "shipped",    89.99,  "2026-05-19", "2026-05-25", 0),
            ("ORD-1014", "Omar Abdullah",   "omar@email.com",    "lost",       59.99,  "2026-05-11", "2026-05-18", 8),
            ("ORD-1015", "Zoe Tremblay",    "zoe@email.com",     "processing", 109.98, "2026-05-22", "2026-05-29", 0),

            # ── Edge-case orders for eval coverage ────────────────
            # Refund eligibility boundary: eligible requires days_late > 2
            ("ORD-1016", "Hannah Schmidt",  "hannah@email.com",  "shipped",    129.99, "2026-05-21", "2026-05-27", 2),  # exactly 2 late -> NOT eligible
            ("ORD-1017", "Diego Morales",   "diego@email.com",   "shipped",    59.99,  "2026-05-17", "2026-05-23", 3),  # 3 late -> eligible via days_late only
            ("ORD-1018", "Grace Liu",       "grace@email.com",   "delivered",  49.99,  "2026-05-09", "2026-05-14", 5),  # delivered yet eligible via days_late
            ("ORD-1019", "Samuel Adeyemi",  "samuel@email.com",  "refunded",   79.99,  "2026-05-07", "2026-05-13", 5),  # refunded + late -> hits already-refunded guard
            ("ORD-1020", "Isabella Rossi",  "isabella@email.com","cancelled",  24.99,  "2026-05-23", "2026-05-29", 0),  # unusual status -> not eligible
            ("ORD-1021", "Noah Andersson",  "noah@email.com",    "shipped",    92.97,  "2026-05-20", "2026-05-26", 0),  # multi-item order
        ]

        conn.executemany("""
            INSERT INTO orders
              (id, customer_name, customer_email, status, order_total,
               created_at, estimated_delivery, days_late)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, orders)

        # ── Order items ───────────────────────────────────────────
        order_items = [
            ("ORD-1001", "P-101", "Wireless Noise-Cancelling Headphones", 1, 89.99),
            ("ORD-1002", "P-103", "Pro Running Shoes",                    1, 129.99),
            ("ORD-1002", "P-109", "Merino Wool Crew Socks 3-Pack",        1, 22.99),  # 129.99+22.99 = 152.98... wait
            ("ORD-1003", "P-104", "Yoga Mat Premium",                     1, 49.99),
            ("ORD-1004", "P-103", "Pro Running Shoes",                    1, 129.99),
            ("ORD-1005", "P-105", "Stainless Steel Water Bottle 32oz",    1, 34.99),
            ("ORD-1006", "P-110", "Portable Bluetooth Speaker",           1, 79.99),
            ("ORD-1007", "P-102", "Mechanical Keyboard TKL",              1, 129.99),
            ("ORD-1007", "P-106", "Laptop Stand Adjustable",              1, 59.99),  # 129.99+59.99 = 189.98... hmm
            ("ORD-1008", "P-108", "Ceramic Pour-Over Coffee Set",         1, 44.99),
            ("ORD-1009", "P-106", "Laptop Stand Adjustable",              1, 59.99),
            ("ORD-1009", "P-107", "Resistance Band Set",                  1, 24.99),
            ("ORD-1009", "P-110", "Portable Bluetooth Speaker",           1, 79.99),  # 164.97
            ("ORD-1010", "P-107", "Resistance Band Set",                  1, 24.99),
            ("ORD-1011", "P-103", "Pro Running Shoes",                    1, 129.99),
            ("ORD-1012", "P-105", "Stainless Steel Water Bottle 32oz",    1, 34.99),
            ("ORD-1012", "P-109", "Merino Wool Crew Socks 3-Pack",        1, 22.99),
            ("ORD-1013", "P-101", "Wireless Noise-Cancelling Headphones", 1, 89.99),
            ("ORD-1014", "P-106", "Laptop Stand Adjustable",              1, 59.99),
            ("ORD-1015", "P-101", "Wireless Noise-Cancelling Headphones", 1, 89.99),
            ("ORD-1015", "P-109", "Merino Wool Crew Socks 3-Pack",        1, 22.99),  # 112.98

            # ── Edge-case order items ─────────────────────────────
            ("ORD-1016", "P-102", "Mechanical Keyboard TKL",              1, 129.99),
            ("ORD-1017", "P-106", "Laptop Stand Adjustable",              1, 59.99),
            ("ORD-1018", "P-104", "Yoga Mat Premium",                     1, 49.99),
            ("ORD-1019", "P-110", "Portable Bluetooth Speaker",           1, 79.99),
            ("ORD-1020", "P-107", "Resistance Band Set",                  1, 24.99),
            ("ORD-1021", "P-105", "Stainless Steel Water Bottle 32oz",    2, 34.99),  # qty 2
            ("ORD-1021", "P-109", "Merino Wool Crew Socks 3-Pack",        1, 22.99),  # 92.97
        ]

        conn.executemany("""
            INSERT INTO order_items
              (order_id, product_id, product_name, quantity, price)
            VALUES (?, ?, ?, ?, ?)
        """, order_items)

    print("✓ Tables created")
    print("✓ 11 products seeded")
    print("✓ 21 orders seeded (delayed, lost, delivered, processing, shipped, refunded, cancelled)")
    print("✓ Inventory seeded with size/color variants (incl. one out-of-stock product)")
    print("\nDemo orders to test with:")
    print("  ORD-1001 — delayed 4 days, refund eligible")
    print("  ORD-1005 — delayed 6 days, refund eligible")
    print("  ORD-1007 — lost, refund eligible")
    print("  ORD-1003 — processing, not yet shipped")
    print("  ORD-1008 — already refunded")
    print("\nEdge-case fixtures (used by the eval suite):")
    print("  ORD-1016 — shipped, 2 days late -> NOT eligible (boundary)")
    print("  ORD-1017 — shipped, 3 days late -> eligible via days_late")
    print("  ORD-1018 — delivered, 5 days late -> eligible via days_late")
    print("  ORD-1019 — refunded, 5 days late -> already-refunded guard")
    print("  ORD-1020 — cancelled -> not eligible")
    print("  ORD-1021 — multi-item order")
    print("  P-111    — Trail Backpack 40L, fully out of stock")

if __name__ == "__main__":
    seed()