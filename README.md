# Smart Memory Agent

AI agent with persistent three-tier memory that remembers past conversations, uses tools, and shows real-time reasoning. Built with FastAPI, ChromaDB, React, and open-source LLMs.

Inspired by [Mem0](https://github.com/mem0ai/mem0), [Letta/MemGPT](https://github.com/letta-ai/letta), and [A-Mem (NeurIPS 2025)](https://arxiv.org/abs/2502.12110).

## How It Works

```
User: "I just got promoted to Senior Engineer at BlackNGreen"

Agent:
  1. Searches memory → finds "User works at BlackNGreen as AI Engineer"
  2. Detects update → "AI Engineer" → "Senior Engineer"
  3. Updates entity memory with new role
  4. Recalls: "User was preparing for promotion last week"
  5. Responds: "Congratulations! I remember you were preparing for this."
  6. Saves new memory in background

Next day:
  User: "Help with my new responsibilities"
  Agent: "Since your promotion to Senior Engineer last week..."
  (Remembered across conversations!)
```

## Architecture

```
┌──────────────┐                    ┌─────────────────────┐
│   React UI    │ ── SSE stream ──→ │   FastAPI Backend    │
│              │                    │                     │
│  Chat        │                    │  Memory Router      │
│  + Thinking  │                    │    ↓ (parallel)     │
│    Panel     │                    │  ┌─────────────┐    │
│              │                    │  │ Short-term   │    │
│  Memory Bank │                    │  │ (RAM buffer) │    │
│  History     │                    │  ├─────────────┤    │
│  Settings    │                    │  │ Long-term    │    │
│              │                    │  │ (ChromaDB)   │    │
└──────────────┘                    │  ├─────────────┤    │
                                    │  │ Entity       │    │
                                    │  │ (SQLite)     │    │
                                    │  └─────────────┘    │
                                    │       ↓             │
                                    │  ReAct Agent Loop   │
                                    │  Think → Act → Obs  │
                                    │       ↓             │
                                    │  Tools: search,     │
                                    │  calc, code exec,   │
                                    │  memory read/write  │
                                    │       ↓             │
                                    │  Self-Correction    │
                                    │       ↓             │
                                    │  Groq / Ollama LLM  │
                                    └─────────────────────┘
```

## Three Types of Memory

| Memory | What It Stores | How It Works | Analogy |
|--------|---------------|-------------|---------|
| **Short-term** | Current conversation (last 20 msgs) | In-memory list | What was said 5 minutes ago |
| **Long-term** | All past conversations | ChromaDB vectors + recency weighting | A diary from last month |
| **Entity** | Structured facts (name, job, preferences) | LLM extraction → SQLite | Your contact book |

### Recency-Weighted Retrieval
```
final_score = (0.7 × similarity) + (0.3 × recency)
recency = e^(-0.01 × hours_since_created)

Result: Recent relevant memories rank higher than old ones,
even if the old memory has slightly better semantic match.
```

## Features

- **Persistent Memory** — Remembers across conversations (not just within one chat)
- **Three-Tier Memory** — Short-term buffer + long-term vectors + structured entities
- **ReAct Reasoning** — Visible Think → Act → Observe loop (streamed to UI)
- **8 Tools** — Web search, calculator, code execution, datetime, memory search, memory save
- **Self-Correction** — Validates answers before responding (catches hallucinations)
- **Memory Router** — Skips unnecessary memory stores for faster response
- **Parallel Search** — All memory tiers queried simultaneously via asyncio
- **Conflict Detection** — Detects contradictory facts, updates instead of duplicating
- **Privacy Controls** — PII detection (Aadhaar, phone, passwords) + "forget" command
- **Real-time UI** — SSE streaming shows agent thinking, tool calls, memory reads/writes
- **Memory Dashboard** — View, search, edit, delete all stored memories

## Quick Start

### 1. Clone and configure

```bash
git clone https://github.com/Ravi10048/smart-agent.git
cd smart-agent

cp .env.example .env
# Edit .env → add your GROQ_API_KEY (free from https://console.groq.com)
```

### 2. Start backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

uvicorn app.main:app --reload --port 8090
```

### 3. Start frontend (separate terminal)

```bash
cd frontend
npm install
npm run dev
```

Open **http://localhost:5173** and start chatting!

## Code Flow (Step-by-Step)

### Step 1: User Sends Message → `routers/chat.py`
```
POST /api/chat (SSE endpoint)
  → Creates conversation if new
  → Saves user message to DB
  → Prefetches user entities into cache (Latency #5)
  → Loads short-term from DB (conversation continuity)
  → Checks for special commands ("forget my ...")
  → Spawns ReAct agent loop
```

### Step 2: Memory Retrieval → `memory/manager.py`
```
Memory Router classifies query (memory/router.py):
  "Hello" → skip all memory (0ms)
  "What's my job?" → entity only (100ms)
  "What did I tell you last week?" → long-term + entity (400ms)

Parallel search via asyncio.gather:
  Short-term: last N messages from RAM buffer
  Long-term: ChromaDB similarity search + recency weighting
  Entity: SQLite lookup with LRU cache
```

### Step 3: ReAct Reasoning → `agent/react_loop.py`
```
for iteration in range(5):
    THOUGHT: "User asks about stocks. Let me check memory..."
    ACTION: search_memory("user stock holdings")
    OBSERVATION: "User owns 100 Infosys shares at ₹1500"
    
    THOUGHT: "Need current price..."
    ACTION: web_search("Infosys stock price today")
    OBSERVATION: "₹1,580.25"
    
    THOUGHT: "Calculate profit..."
    ACTION: calculator("(1580.25 - 1500) * 100")
    OBSERVATION: "8025.0"
    
    FINAL ANSWER: "Your 100 Infosys shares are worth ₹1,58,025..."
```

### Step 4: Self-Correction → `agent/validator.py`
```
Before sending response:
  → LLM validates: are facts from memory? calculations correct?
  → If invalid → corrects the response
  → Returns confidence score
```

### Step 5: Stream to Frontend → SSE Events
```
{"type": "thinking",     "content": "Checking memory..."}
{"type": "memory_read",  "store": "entity", ...}
{"type": "tool_call",    "tool": "web_search", ...}
{"type": "tool_result",  "tool": "web_search", ...}
{"type": "self_check",   "confident": true, ...}
{"type": "token",        "content": "Your "}
{"type": "token",        "content": "Infosys "}
{"type": "memory_write", "content": "Saving to memory..."}
{"type": "done",         ...}
```

### Step 6: Background Memory Write → `memory/manager.py`
```
After response sent (non-blocking via asyncio.create_task):
  → LLM extracts entities from conversation
  → Conflict check against existing entities
  → Store/update in SQLite (entity memory)
  → Embed conversation turn into ChromaDB (long-term)
  → PII filter applied before storage
```

## 5 Latency Optimizations

| # | Optimization | How | Impact |
|---|-------------|-----|--------|
| 1 | **Parallel search** | `asyncio.gather` on all 3 memory stores | Sum → Max (saves ~150ms) |
| 2 | **Memory router** | LLM classifier skips unnecessary stores | Saves 400ms+ for simple queries |
| 3 | **Streaming** | User sees thinking + tokens immediately | Perceived latency ~0ms |
| 4 | **LRU cache** | Hot entities cached in RAM | 0ms vs 100ms DB hit |
| 5 | **Pre-fetch** | Load user profile on conversation start | First query 100-400ms faster |

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Backend** | Python, FastAPI, SQLAlchemy, SQLite |
| **Vector DB** | ChromaDB (embedded, no server needed) |
| **Embeddings** | sentence-transformers `all-MiniLM-L6-v2` |
| **LLM** | Groq (Llama 3.3 70B, free) + Ollama (self-hosted) |
| **Streaming** | Server-Sent Events (SSE) |
| **Frontend** | React, TypeScript, Tailwind CSS |
| **Tools** | DuckDuckGo search, safe math eval, sandboxed Python exec |

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/chat` | SSE streaming chat |
| `GET` | `/api/conversations` | List conversations |
| `GET` | `/api/conversations/:id` | Get conversation with messages |
| `DELETE` | `/api/conversations/:id` | Delete conversation |
| `GET` | `/api/memory/entities` | List all entities |
| `PUT` | `/api/memory/entities/:id` | Edit entity |
| `DELETE` | `/api/memory/entities/:id` | Delete entity |
| `GET` | `/api/memory/long-term` | List long-term memories |
| `DELETE` | `/api/memory/long-term/:id` | Delete memory |
| `POST` | `/api/memory/search` | Search across all memory |
| `POST` | `/api/memory/forget` | Forget specific info |
| `GET` | `/api/settings` | App settings |
| `GET` | `/api/settings/health` | LLM health check |

## Project Structure

```
smart-agent/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI entry point
│   │   ├── config.py            # Settings
│   │   ├── memory/
│   │   │   ├── short_term.py    # RAM buffer (last N messages)
│   │   │   ├── long_term.py     # ChromaDB with recency weighting
│   │   │   ├── entity_store.py  # LLM extraction + conflict detection
│   │   │   ├── router.py        # Decides which stores to check
│   │   │   ├── manager.py       # Orchestrates parallel search
│   │   │   ├── privacy.py       # PII filter + forget command
│   │   │   └── consolidator.py  # Decay + cleanup
│   │   ├── agent/
│   │   │   ├── react_loop.py    # Think → Act → Observe engine
│   │   │   ├── prompts.py       # System prompts + ReAct template
│   │   │   └── validator.py     # Self-correction
│   │   ├── tools/               # 8 tools (search, calc, code, memory)
│   │   ├── llm/                 # Groq + Ollama with streaming
│   │   ├── routers/             # Chat SSE, memory, conversations, settings
│   │   └── db/                  # SQLAlchemy models + repository
│   └── tests/
├── frontend/
│   └── src/
│       ├── pages/               # Chat, MemoryBank, History, Settings
│       ├── components/          # ChatMessage, ThinkingPanel, MemoryCard
│       └── api/                 # API client + SSE streaming helper
└── README.md
```

## License

MIT
