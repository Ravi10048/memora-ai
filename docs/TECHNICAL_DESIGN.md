# Smart Memory Agent — Technical Design Document

## System Overview

An AI agent with three-tier persistent memory (short-term, long-term, entity), ReAct reasoning with tool-calling, self-correction, and real-time streaming UI. Inspired by Mem0, Letta/MemGPT, and A-Mem (NeurIPS 2025).

---

## Design Decisions & Trade-offs

### 1. Why Three Separate Memory Tiers Instead of One?

**Decision:** Separate short-term (RAM), long-term (ChromaDB), and entity (SQLite) stores.

**Why:**
- Short-term needs instant access (O(1) list lookup) — vector search is overkill for 20 messages.
- Long-term needs semantic similarity search across thousands of memories — only a vector DB can do this.
- Entities need structured queries ("What is user's company?") — SQL is more precise than vector similarity for exact fact lookups.

**Trade-off:** Three stores means three codepaths to maintain. A single store (like just ChromaDB) would be simpler but worse at each task.

### 2. Why ChromaDB Over Pinecone/Qdrant/Weaviate?

**Decision:** ChromaDB in embedded mode (no separate server).

**Why:**
- Zero infrastructure — runs inside the Python process. No Docker container, no API key, no server.
- Perfect for a portfolio project and small-to-medium scale.
- Persistent storage to disk — survives process restarts.

**Trade-off:** Not suitable for multi-server deployment. Pinecone or Qdrant would be needed for production scale (millions of memories).

### 3. Why Memory Router Instead of Always Searching Everything?

**Decision:** A lightweight LLM call classifies each query to decide which memory stores to check.

**Why:**
- A casual "hello" doesn't need a 400ms vector search.
- The router call is ~100 tokens, ~100ms on Groq — saves 400ms+ by skipping unnecessary searches.
- Net latency improvement: -300ms for simple queries, +100ms for complex queries.

**Trade-off:** Extra LLM call per message. The router could misclassify — if it skips long-term when it shouldn't, the agent won't have context. Mitigated by defaulting to "check everything" on classification failure.

### 4. Why ReAct Over Chain-of-Thought or Plan-and-Execute?

**Decision:** ReAct (Reason + Act) pattern with Think → Act → Observe loop.

**Why:**
- Most natural fit for tool-using agents — the agent can interleave reasoning with actions.
- Easy to stream to the UI — each step (thought, action, observation) becomes a visual event.
- Well-understood pattern with strong research backing.

**Trade-off:** Can get stuck in loops (thinking → acting → thinking again without converging). Mitigated by MAX_ITERATIONS=5 cap. Plan-and-Execute might be better for very complex multi-step tasks, but ReAct is more appropriate for conversational agents.

### 5. Why Self-Correction as a Separate Step?

**Decision:** After the ReAct loop produces an answer, a separate LLM call validates it.

**Why:**
- Catches hallucinated memories ("I remember you said X" when you never did).
- Catches calculation errors.
- Adds a confidence score to the response.

**Trade-off:** Extra LLM call (~200ms, ~100 tokens). Only triggered when the response references memory or tool results. Skipped for simple responses.

### 6. Why Background Memory Write Instead of Inline?

**Decision:** Entity extraction and long-term storage happen AFTER the response is sent, via `asyncio.create_task()`.

**Why:**
- Entity extraction needs an LLM call (~500ms). If done before responding, user waits an extra 500ms for every message.
- Background write means the user gets their response immediately. Memory catches up asynchronously.

**Trade-off:** If the server crashes during background write, that conversation turn's entities are lost. Acceptable for a portfolio project — production would use a task queue.

---

## Known Gaps & Solutions

### Gap 1: Wrong Entity Extraction

**Problem:** LLM extracts wrong facts. "My friend Amit works at Google" → LLM stores "User works at Google" (wrong subject).

**Impact:** Agent gives incorrect information based on misattributed facts.

**Current mitigation:**
- Extraction prompt explicitly instructs: "Distinguish between facts about the USER vs OTHER people they mention."
- Example included in prompt showing correct vs incorrect extraction.

**Future solution:**
- Two-step extraction: Step 1 extracts, Step 2 validates with a second LLM call ("Does the original text say USER works at Google?").
- Only validate entity memory (structured facts are critical), not long-term (less precise is ok).

### Gap 2: Memory Grows Forever

**Problem:** After 1000 conversations, ChromaDB has thousands of embeddings. Search gets slower and results get noisier.

**Impact:** Slow retrieval, irrelevant old memories polluting results.

**Current mitigation:**
- `consolidator.py` implements decay scoring: `importance = importance × e^(-0.005 × hours_since_access)`.
- Memories untouched for 60 days with importance below 0.1 are deleted.
- Frequently accessed memories get boosted: `importance += min(access_count × 0.05, 0.3)`.

**Future solution:**
- Merge similar memories: detect near-duplicate embeddings, consolidate into one.
- Periodic background job (cron) runs consolidation automatically.
- Hierarchical summarization: old detailed memories → summarized versions.

### Gap 3: Context Window Overflow

**Problem:** Too many memories retrieved → prompt exceeds LLM context window (32K tokens for Llama 3.3).

**Impact:** LLM crashes, truncates, or produces degraded output.

**Current mitigation:**
- `token_counter.py` enforces budget allocation: system (1500) + entity (500) + short-term (3000) + long-term (2000) + tools (1000) + response (4000) = ~12500 tokens.
- Short-term: if exceeds budget, summarize oldest messages.
- Long-term: keep only top-K results by score.
- `truncate_to_budget()` function enforces hard character limits.

**Future solution:**
- Dynamic budgeting based on query complexity (simple queries get more response space, complex queries get more memory space).
- Streaming summarization of short-term when approaching limit.

### Gap 4: Contradictory Facts

**Problem:** User says contradictory things across conversations. "I'm vegetarian" (Monday) vs "I had chicken biryani" (Friday).

**Impact:** Agent stores both, gives inconsistent answers.

**Current mitigation:**
- `entity_store.py` detects when a new attribute conflicts with an existing one for the same entity.
- Merge strategy: new values overwrite old values for the same key.
- Conflict is logged for observability.

**Future solution:**
- Confidence-based resolution:
  - Explicit contradiction ("I'm no longer vegetarian") → overwrite, high confidence
  - Implicit contradiction ("I had chicken") → store both, lower confidence on old
  - Ambiguous → ask the user on next retrieval
- LLM-powered conflict resolver: use `CONFLICT_CHECK_PROMPT` to classify and resolve.

### Gap 5: Sensitive Data Stored

**Problem:** User says "My password is abc123" or shares Aadhaar/PAN number. Stored in SQLite/ChromaDB on disk.

**Impact:** Security and privacy risk. Data breach potential.

**Current mitigation:**
- `privacy.py` has regex patterns for: Aadhaar (12 digits), PAN (ABCDE1234F), phone (10 digits), passwords, API keys, card numbers, SSN.
- `contains_sensitive_data()` checks before storing.
- `redact_sensitive_data()` replaces matches with `[REDACTED]`.
- `memory_save.py` tool refuses to save sensitive content.
- "Forget" command: user says "forget my password" → deletes matching entities + long-term memories.

**Future solution:**
- Encryption at rest for SQLite entities.
- Configurable PII rules per deployment.
- Audit log of all memory writes for compliance.

### Gap 6: Multi-User Memory Mix

**Problem:** Two users share deployment → one user's memories could leak to another.

**Impact:** Privacy violation. User A sees User B's data.

**Current mitigation:**
- Every database query and ChromaDB search is scoped by `user_id`.
- `manager.py` passes `user_id` to every memory operation.
- ChromaDB `where={"user_id": user_id}` filter on every query.
- Default user_id is "default" for single-user deployments.

**Future solution:**
- Authentication layer (JWT/session) that automatically sets user_id.
- Separate ChromaDB collections per user (stronger isolation).
- Row-level security policies in database.

### Gap 7: Irrelevant Vector Search Results

**Problem:** ChromaDB similarity search returns semantically related but contextually irrelevant results. "How's the weather?" returns "User likes to go for walks" (similarity: 0.78).

**Impact:** Wrong context injected into prompt → agent gives confused responses.

**Current mitigation:**
- `long_term.py` enforces `MIN_RELEVANCE_SCORE = 0.75` (configurable via env).
- Results below threshold are filtered out.
- Recency weighting further deprioritizes old, tangentially related memories.
- Better to have NO context than WRONG context.

**Future solution:**
- Two-stage retrieval: Stage 1 = vector search (broad recall). Stage 2 = LLM re-ranker (precision).
- Query expansion: rephrase the query before searching for better matches.

### Gap 8: Embedding Model Change Breaks Old Memories

**Problem:** Memories embedded with model A can't be searched if you switch to model B (different dimensions, different vector space).

**Impact:** All existing memories become unsearchable. Effective memory loss.

**Current mitigation:**
- `MemoryMetadata` table stores `original_text` and `embedding_model` alongside every ChromaDB entry.
- On model change: can re-embed all memories from stored text in a background job.

**Future solution:**
- Automatic migration script: detect model change → re-embed all memories.
- Version tracking: tag each memory with its embedding model version.

### Gap 9: Agent Hallucinating Memories

**Problem:** Agent says "I remember you said X" but user never said X. LLM generated a plausible but false memory.

**Impact:** User loses trust. Factually wrong responses based on non-existent memories.

**Current mitigation:**
- System prompt: "ONLY state facts from your memory stores. If you don't have it stored, say so. NEVER make up facts about the user."
- Entity records include `source_message_id` and `source_conversation_id` for citation.
- `validator.py` checks: "Does the response only reference facts from memory or tool results?"

**Future solution:**
- Citation display in UI: "I know your company is BlackNGreen [source: conversation on April 3]."
- Clickable citations that link back to the original message.
- Confidence threshold: only cite memories with confidence > 0.7.

---

## Future Roadmap

### Phase 1: Memory Quality
- [ ] Two-step entity extraction (extract + validate)
- [ ] LLM-powered conflict resolution
- [ ] Two-stage retrieval (vector search + LLM re-ranker)
- [ ] Citation display in UI with source links
- [ ] Automatic memory consolidation cron job

### Phase 2: Agent Intelligence
- [ ] Multi-agent collaboration (specialist agents for different domains)
- [ ] Plan-and-Execute for complex multi-step tasks
- [ ] Learning from feedback (user corrections improve future responses)
- [ ] Tool creation (agent can define new tools from user descriptions)

### Phase 3: Scale & Security
- [ ] Authentication (JWT/OAuth)
- [ ] PostgreSQL migration for concurrent users
- [ ] Separate ChromaDB collections per user
- [ ] Encryption at rest for sensitive entities
- [ ] Rate limiting per user

### Phase 4: Advanced Memory
- [ ] Episodic memory (detailed scene-like recollections with context)
- [ ] Procedural memory (learned workflows and procedures)
- [ ] Memory graph visualization (entity relationships as a visual graph)
- [ ] Cross-user knowledge sharing (opt-in shared knowledge base)

---

## Performance Characteristics

| Metric | Current | Target |
|--------|---------|--------|
| Time to first token | 400-800ms | < 400ms |
| Memory search (cache hit) | 0ms | 0ms |
| Memory search (cache miss) | 400ms | 200ms (with re-ranker) |
| Entity extraction (background) | 500ms | 300ms |
| Max concurrent users | 1 (SQLite) | 100+ (PostgreSQL) |
| Memory capacity | ~10K memories/user | ~100K (with consolidation) |

---

## Security Considerations

1. **PII Detection:** Regex-based filter for Aadhaar, PAN, phone, passwords, API keys, card numbers. Applied before all memory writes.
2. **Forget Command:** User can delete specific memories at any time. Deletes from both SQLite and ChromaDB.
3. **User Isolation:** Every query scoped by user_id. No cross-user memory leakage.
4. **No Code Persistence:** Code executor uses temp files, deleted immediately after execution.
5. **Groq vs Ollama:** For sensitive data, use Ollama (fully local). Groq sends data to cloud API.
6. **Secrets in .env:** API keys, database URL — all in `.env`, which is `.gitignore`d.

---

## Research References

- [Mem0: Building Production-Ready AI Agents with Scalable Long-Term Memory](https://arxiv.org/abs/2504.19413)
- [A-Mem: Agentic Memory for LLM Agents (NeurIPS 2025)](https://arxiv.org/abs/2502.12110)
- [Letta/MemGPT: Towards LLMs as Operating Systems](https://docs.letta.com/concepts/memgpt/)
- [Agentic Memory: Unified Long-Term and Short-Term Memory Management](https://arxiv.org/abs/2601.01885)
- [Memory Mechanisms in LLM Agents](https://www.emergentmind.com/topics/memory-mechanisms-in-llm-based-agents)
