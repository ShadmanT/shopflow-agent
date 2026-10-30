import json
import sys
import os
sys.path.append(os.path.dirname(__file__))
from database import get_order, refund_order, get_product, get_inventory, create_escalation
from knowledge_base import search_knowledge_base

# ── Tool schemas (what Claude sees) ───────────────────────────────────────────

TOOL_DEFINITIONS = [
    {
        "name": "check_order_status",
        "description": (
            "Look up the current status of a customer's order by order ID. "
            "Returns order details, items, shipping status, and whether the order "
            "is eligible for a refund. Always call this before process_refund."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "order_id": {
                    "type": "string",
                    "description": "The order ID, e.g. 'ORD-1001'. If the customer provides just a number like '1001', prepend 'ORD-'."
                }
            },
            "required": ["order_id"]
        }
    },
    {
        "name": "process_refund",
        "description": (
            "Process a refund for a customer's order. Call this only after (1) check_order_status "
            "confirms the order is refund eligible AND (2) the customer has explicitly confirmed "
            "they want the refund. Before calling, tell the customer the order ID and the exact "
            "refund amount and ask them to confirm; call this only once they say yes. "
            "Never ask permission to look up an order — only the refund itself needs confirmation."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "order_id": {
                    "type": "string",
                    "description": "The order ID to refund"
                },
                "reason": {
                    "type": "string",
                    "description": "Reason for the refund, e.g. 'delayed shipment', 'lost package', 'damaged item'"
                }
            },
            "required": ["order_id", "reason"]
        }
    },
    {
        "name": "check_inventory",
        "description": (
            "Check current stock levels for a product. "
            "Returns total stock and a breakdown by size and color variants. "
            "Search by product ID if known, otherwise by product name."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "product_id": {
                    "type": "string",
                    "description": "Product ID if known, e.g. 'P-101'"
                },
                "product_name": {
                    "type": "string",
                    "description": "Product name to search if no ID available, e.g. 'headphones'"
                }
            },
            "required": []
        }
    },
    {
        "name": "get_product_info",
        "description": (
            "Get full details for a product: description, price, specs, colors, "
            "sizes, and customer ratings. Search by product ID or name."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "product_id": {
                    "type": "string",
                    "description": "Product ID if known"
                },
                "product_name": {
                    "type": "string",
                    "description": "Product name to search if no ID available"
                }
            },
            "required": []
        }
    },
    {
        "name": "escalate_to_human",
        "description": (
            "Escalate a customer issue to a human support agent by creating a ticket. "
            "Use this when the issue cannot be resolved automatically — suspected fraud, "
            "account access problems, legal complaints, or policy exceptions. "
            "Always use this as a last resort after attempting to resolve the issue."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "reason": {
                    "type": "string",
                    "description": "Why escalation is needed"
                },
                "urgency": {
                    "type": "string",
                    "enum": ["low", "medium", "high"],
                    "description": "low = general inquiry, medium = frustrated customer, high = fraud or legal"
                },
                "order_id": {
                    "type": "string",
                    "description": "Related order ID if applicable"
                },
                "summary": {
                    "type": "string",
                    "description": "Brief context for the human agent picking up this ticket"
                }
            },
            "required": ["reason", "urgency"]
        },

    },
    {
        "name": "search_knowledge_base",
        "description": (
            "Search ShopFlow's internal knowledge base for policy information. "
            "Use this to answer questions about return policies, shipping times, "
            "warranty coverage, and store policies. "
            "Always search here before answering policy questions from memory."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The policy question to search for, e.g. 'return window for damaged items'"
                }
            },
            "required": ["query"]
        }
    }

]


# ── Tool executor (what your code runs) ───────────────────────────────────────

def execute_tool(name: str, inputs: dict) -> dict:
    """
    Dispatch a tool call from Claude to the right function.
    Always returns a dict — never raises. Errors come back as
    structured dicts so Claude can reason over them.
    """
    try:
        if name == "check_order_status":
            result = get_order(inputs["order_id"])
            if result is None:
                return {
                    "error": f"No order found with ID '{inputs['order_id']}'",
                    "suggestion": "Ask the customer to double-check their order ID"
                }
            return result

        elif name == "process_refund":
            return refund_order(inputs["order_id"], inputs["reason"])

        elif name == "check_inventory":
            result = get_inventory(
                product_id=inputs.get("product_id"),
                product_name=inputs.get("product_name")
            )
            if result is None:
                return {"error": "Product not found", "query": inputs}
            return result

        elif name == "get_product_info":
            result = get_product(
                product_id=inputs.get("product_id"),
                product_name=inputs.get("product_name")
            )
            if result is None:
                return {"error": "Product not found", "query": inputs}
            return result

        elif name == "escalate_to_human":
            return create_escalation(
                order_id=inputs.get("order_id"),
                reason=inputs["reason"],
                urgency=inputs["urgency"],
                summary=inputs.get("summary")
            )
        
        elif name == "search_knowledge_base":
            return search_knowledge_base(inputs["query"])

        else:
            return {"error": f"Unknown tool: {name}"}

    except Exception as e:
        return {"error": f"Tool execution failed: {str(e)}", "tool": name, "inputs": inputs}