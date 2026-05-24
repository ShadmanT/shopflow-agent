import os
import json
import anthropic
import sys
sys.path.append(os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv()

from knowledge_base import build_knowledge_base
build_knowledge_base()

from tools import TOOL_DEFINITIONS, execute_tool

client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

SYSTEM_PROMPT = """You are Aria, a customer support agent for ShopFlow, a mid-size e-commerce platform.

## Your capabilities
You have access to tools to check order status, process refunds, look up product inventory, get product details, and escalate issues to human agents.

## How to handle requests
- Always look up real data before answering. Never guess or assume order status, inventory, or product details.
- If a customer mentions an order issue, check the order status first — then decide what action to take.
- If an order is eligible for a refund, process it directly. Do not ask for permission.
- If you can fully resolve the issue, do so. Only escalate when you genuinely cannot help.

## When to escalate
Escalate immediately for: suspected fraud, account hacking, legal threats, requests for exceptions beyond your tools, or anything requiring a human judgment call.

## Tone
Professional and warm. One sentence of empathy maximum, then solve the problem. Be concise — customers are frustrated, they want resolution not conversation.

## Format
Plain prose only. No bullet points, no markdown headers, no bold text. Write like a human support agent, not a document."""


def run_agent(messages: list[dict]) -> dict:
    """
    Run the agentic loop until Claude stops calling tools.
    Returns the final text response and a list of tools that were called.
    """
    tools_used = []

    # Prepend system context to message history
    loop_messages = list(messages)

    while True:
        response = client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            tools=TOOL_DEFINITIONS,
            messages=loop_messages
        )

        # Claude is done — return final response
        if response.stop_reason == "end_turn":
            final_text = next(
                (block.text for block in response.content if hasattr(block, "text")),
                "I wasn't able to generate a response. Please try again."
            )
            return {
                "response": final_text,
                "tools_used": tools_used
            }

        # Claude wants to call tools
        if response.stop_reason == "tool_use":
            # Add Claude's response (including tool_use blocks) to history
            loop_messages.append({
                "role": "assistant",
                "content": response.content
            })

            # Execute every tool Claude requested
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    tools_used.append(block.name)

                    result = execute_tool(block.name, block.input)

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(result)
                    })

            # Add tool results to history and loop
            loop_messages.append({
                "role": "user",
                "content": tool_results
            })

        else:
            # Unexpected stop reason — bail out cleanly
            return {
                "response": "Something unexpected happened. Please try again.",
                "tools_used": tools_used
            }


def stream_agent(messages: list[dict]):
    """
    Generator that yields events as tools fire.
    Types: tool_start | tool_result | response | error
    """
    loop_messages = list(messages)

    while True:
        try:
            with client.messages.stream(
                model="claude-sonnet-4-5",
                max_tokens=1024,
                system=SYSTEM_PROMPT,
                tools=TOOL_DEFINITIONS,
                messages=loop_messages
            ) as stream:
                full_response = stream.get_final_message()
        except Exception as e:
            yield {"type": "error", "message": str(e)}
            return

        if full_response.stop_reason == "end_turn":
            text = next(
                (block.text for block in full_response.content if hasattr(block, "text")),
                "I wasn't able to generate a response. Please try again."
            )
            yield {"type": "response", "text": text}
            return

        if full_response.stop_reason == "tool_use":
            loop_messages.append({
                "role": "assistant",
                "content": full_response.content
            })

            tool_results = []
            for block in full_response.content:
                if block.type == "tool_use":
                    yield {
                        "type": "tool_start",
                        "tool": block.name,
                        "input": block.input,
                        "id": block.id
                    }

                    result = execute_tool(block.name, block.input)

                    yield {
                        "type": "tool_result",
                        "tool": block.name,
                        "result": result,
                        "id": block.id
                    }

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(result)
                    })

            loop_messages.append({
                "role": "user",
                "content": tool_results
            })
        else:
            yield {"type": "error", "message": f"Unexpected stop: {full_response.stop_reason}"}
            return