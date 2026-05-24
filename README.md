# ShopFlow Agent

An AI customer support agent for a fictional e-commerce store, built with Claude's tool use API. The agent can look up orders, process refunds, check inventory, search policy docs, and escalate to human agents — all through multi-step tool calls.

Built as a portfolio project targeting roles at companies building conversational AI agents (Affirm, Cresta, CommerceIQ, Maxima).

---

## What it demonstrates

- **Agentic loop** — Claude runs in a while loop, calling tools until the issue is resolved. A single user message can trigger multiple sequential tool calls.
- **Tool use** — 6 tools wired to a real SQLite database and a vector knowledge base.
- **RAG** — Policy docs chunked, embedded via OpenAI, and stored in ChromaDB. Claude retrieves relevant chunks to answer policy questions accurately.
- **Real state mutation** — Refunds actually update the database. Escalations write tickets to a table.
- **Graceful error handling** — Tools never throw. Errors return structured dicts so Claude can reason over failures and respond naturally.

---

## Tools

| Tool | What it does |
|---|---|
| `check_order_status` | Looks up order by ID, returns status and refund eligibility |
| `process_refund` | Updates order to refunded, returns confirmation number |
| `check_inventory` | Returns stock levels by size and color variant |
| `get_product_info` | Returns product details, specs, ratings |
| `escalate_to_human` | Creates a support ticket with urgency level |
| `search_knowledge_base` | RAG search over returns, shipping, and warranty policy docs |

---

## Tech stack

| Layer | Tech |
|---|---|
| Agent / LLM | Claude claude-sonnet-4-5 via Anthropic API |
| Embeddings | OpenAI text-embedding-3-small |
| Vector store | ChromaDB (local persistent) |
| Backend | Python, FastAPI, uvicorn |
| Database | SQLite |
| Frontend | React, Vite |

---

## Project structure

```
shopflow-agent/
├── backend/
│   ├── main.py              # FastAPI app, CORS, /chat endpoint
│   ├── agent.py             # Agentic loop
│   ├── tools.py             # Tool schemas + executor
│   ├── database.py          # SQLite connection + query helpers
│   ├── knowledge_base.py    # ChromaDB setup + RAG search
│   ├── seed.py              # Creates tables and inserts fake data
│   └── docs/                # Policy markdown files for RAG
│       ├── returns_policy.md
│       ├── shipping_faq.md
│       └── warranty.md
└── frontend/
    └── src/
        ├── App.jsx          # Root component, message state
        ├── Message.jsx      # Message bubble with tool badges
        ├── ToolBadge.jsx    # Shows which tools fired
        └── api.js           # fetch wrapper for POST /chat
```

---

## Running locally

### Prerequisites

- Python 3.11+
- Node.js 18+
- Anthropic API key — [console.anthropic.com](https://console.anthropic.com)
- OpenAI API key — [platform.openai.com](https://platform.openai.com)

### Backend

```bash
# From repo root
python -m venv venv
venv\Scripts\activate        # Windows
source venv/bin/activate     # Mac/Linux

pip install -r backend/requirements.txt

# Create backend/.env
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...

# Seed the database
cd backend
python seed.py

# Start the server
uvicorn main:app --reload
```

### Frontend

```bash
# In a new terminal from repo root
cd frontend
npm install
npm run dev
```

Open [http://localhost:5173](http://localhost:5173)

---

## Demo scenarios

These show off the most interesting agent behaviors:

**Multi-step refund — 2 tool calls in one message**
```
My order ORD-1001 is late, can I get a refund?
```

**Lost package — immediate refund**
```
Order ORD-1007 never arrived
```

**Fraud escalation — immediate high-urgency ticket**
```
Someone used my account to place order ORD-1009 without my permission
```

**Agent pushes back on wrong information**
```
I've been waiting 3 weeks for ORD-1003 and I'm going to take legal action
```

**RAG policy lookup**
```
What's your return policy for damaged items?
```

**Inventory + product info**
```
Do you have the wireless headphones in stock? What colors?
```

---

## Architecture

```
User → React UI → POST /chat → FastAPI
                                  ↓
                             Agentic loop
                                  ↓
                          Claude (tool_use) ←→ Tool executor
                                                    ↓
                                          SQLite / ChromaDB
```

The agentic loop runs until `stop_reason == "end_turn"`. On each iteration, Claude either returns a final text response or a `tool_use` block. Tool results are appended to the message history and sent back to Claude, which continues reasoning until the issue is resolved.

---

## If I were scaling this

- SQLite → PostgreSQL
- ChromaDB local → Pinecone or Weaviate
- Synchronous tool execution → async with timeout guards
- Single system prompt → prompt versioning and A/B testing
- No auth → JWT with customer identity passed in context