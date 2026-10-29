"""Reset the demo database to its original seeded state.

This is a thin wrapper around seed() so it can never drift from the
canonical fixtures in seed.py. Running it rebuilds products, inventory,
orders, order items, and clears escalations.

    python backend/reset_orders.py
"""
import os
import sys
sys.path.append(os.path.dirname(__file__))

from seed import seed

if __name__ == "__main__":
    seed()
