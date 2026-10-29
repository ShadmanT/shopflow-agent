"""
ShopFlow MCP server.

Exposes the same six capabilities Sage uses — order status, refunds, inventory,
product info, escalation, and policy search — over the Model Context Protocol,
so any MCP client (Claude Desktop, the Claude Messages API MCP connector, other
agents) can call them without knowing anything about ShopFlow's internals.

The tools import the existing business logic from database.py and
knowledge_base.py, so the refund guards, eligibility rules, and structured
error shapes are identical whether a tool is called in-process by agent.py or
over MCP by an external client — one source of truth.

Run it (stdio transport, for Claude Desktop and most MCP clients):

    python backend/mcp_server.py

It expects the SQLite database to be seeded first (python backend/seed.py).
Policy search additionally needs OPENAI_API_KEY to build the vector store; if
that key is absent the server still starts and every non-search tool works.
"""
import os
import sys

sys.path.append(os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv()

from mcp.server.mcpserver import MCPServer

from database import (
    get_order,
    refund_order,
    get_product,
    get_inventory,
    create_escalation,
)

mcp = MCPServer("shopflow")

# Build the policy knowledge base on startup so search_knowledge_base works.
# knowledge_base.py constructs an OpenAI client at import, so import it inside
# the guard too: if OPENAI_API_KEY is missing or embedding fails, the server
# still starts and every non-search tool keeps working.
_kb_search = None
try:
    from knowledge_base import search_knowledge_base as _kb_search, build_knowledge_base
    build_knowledge_base()
except Exception as e:  # pragma: no cover - startup best-effort
    _kb_search = None
    print(f"[mcp] knowledge base unavailable ({e}); search_knowledge_base is disabled", file=sys.stderr)


@mcp.tool()
def check_order_status(order_id: str) -> dict:
    """Look up the current status of a customer's order by order ID.

    Returns order details, items, shipping status, and whether the order is
    eligible for a refund. Always call this before process_refund. If the
    customer provides just a number like '1001', prepend 'ORD-'.
    """
    result = get_order(order_id)
    if result is None:
        return {
            "error": f"No order found with ID '{order_id}'",
            "suggestion": "Ask the customer to double-check their order ID",
        }
    return result


@mcp.tool()
def process_refund(order_id: str, reason: str) -> dict:
    """Process a refund for a customer's order.

    Only call after checking the order status and confirming it is refund
    eligible. Do not ask the customer for permission — if eligible, process it
    directly. Guards against double refunds and ineligible orders.
    """
    return refund_order(order_id, reason)


@mcp.tool()
def check_inventory(product_id: str | None = None, product_name: str | None = None) -> dict:
    """Check current stock levels for a product.

    Returns total stock and a breakdown by size and color variants. Search by
    product ID if known (e.g. 'P-101'), otherwise by product name.
    """
    result = get_inventory(product_id=product_id, product_name=product_name)
    if result is None:
        return {"error": "Product not found", "query": {"product_id": product_id, "product_name": product_name}}
    return result


@mcp.tool()
def get_product_info(product_id: str | None = None, product_name: str | None = None) -> dict:
    """Get full details for a product: description, price, specs, colors, sizes, and ratings.

    Search by product ID or name.
    """
    result = get_product(product_id=product_id, product_name=product_name)
    if result is None:
        return {"error": "Product not found", "query": {"product_id": product_id, "product_name": product_name}}
    return result


@mcp.tool()
def escalate_to_human(reason: str, urgency: str, order_id: str | None = None, summary: str | None = None) -> dict:
    """Escalate a customer issue to a human support agent by creating a ticket.

    Use for issues that cannot be resolved automatically — suspected fraud,
    account access problems, legal complaints, or policy exceptions. urgency is
    one of 'low', 'medium', or 'high'.
    """
    return create_escalation(order_id=order_id, reason=reason, urgency=urgency, summary=summary)


@mcp.tool()
def search_knowledge_base(query: str) -> dict:
    """Search ShopFlow's internal knowledge base for policy information.

    Use to answer questions about return policies, shipping times, warranty
    coverage, and store policies. Always search here before answering policy
    questions from memory.
    """
    if _kb_search is None:
        return {"error": "Knowledge base unavailable (OPENAI_API_KEY not configured)", "results": []}
    return _kb_search(query)


if __name__ == "__main__":
    # stdio transport — what Claude Desktop and most MCP clients expect.
    mcp.run()
