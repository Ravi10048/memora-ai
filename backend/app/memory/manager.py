from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from app.config import settings
from app.db.database import get_db_context
from app.db import repository as repo
from app.llm.base import BaseLLMProvider
from app.memory.short_term import ShortTermMemory
from app.memory.long_term import LongTermMemory, MemoryResult
from app.memory.entity_store import EntityStore
from app.memory.router import MemoryRouter, MemoryRouteDecision
from app.memory.privacy import contains_sensitive_data, redact_sensitive_data, is_forget_command
from app.utils.logger import get_logger
from app.utils.token_counter import truncate_to_budget

logger = get_logger(__name__)


@dataclass
class MemoryContext:
    """Combined context from all memory tiers."""
    short_term: list[dict] = field(default_factory=list)
    long_term: list[MemoryResult] = field(default_factory=list)
    entities: list[dict] = field(default_factory=list)
    entity_context_string: str = ""
    route_decision: MemoryRouteDecision | None = None

    def to_prompt_context(self) -> str:
        """Format all memory into a string for the LLM prompt."""
        parts = []

        if self.entity_context_string:
            parts.append(f"## Entity Memory\n{self.entity_context_string}")

        if self.long_term:
            lt_parts = []
            for mem in self.long_term:
                lt_parts.append(f"- {mem.text} (relevance: {mem.final_score:.2f})")
            parts.append("## Relevant Past Memories\n" + "\n".join(lt_parts))

        if not parts:
            return ""

        full = "\n\n".join(parts)
        return truncate_to_budget(full, "long_term")


class MemoryManager:
    """Orchestrates all three memory tiers with parallel search and caching.

    Implements all 5 latency optimizations:
        1. Parallel search via asyncio.gather
        2. Memory router to skip unnecessary stores
        3. LRU cache in entity store
        4. Pre-fetch on conversation start
        5. Streaming happens at the agent level (not here)
    """

    def __init__(self, llm: BaseLLMProvider | None = None):
        self.llm = llm
        self.short_term = ShortTermMemory()
        self.long_term = LongTermMemory()
        self.entity_store = EntityStore(llm=llm)
        self.router = MemoryRouter(llm=llm)

    async def retrieve(self, query: str, user_id: str) -> MemoryContext:
        """Retrieve relevant context from all memory tiers.

        Latency optimization #1 & #2: route first, then parallel search.
        """
        # Get recent context for the router
        recent = ""
        if self.short_term.size > 0:
            msgs = self.short_term.get_context()[-2:]
            recent = " | ".join(m["content"] for m in msgs)

        # Route: decide which stores to check
        decision = await self.router.route(query, recent)

        # Parallel search only on needed stores
        async def search_short_term():
            if decision.short_term:
                return self.short_term.search(query)
            return []

        async def search_long_term():
            if decision.long_term:
                results = self.long_term.search(query, user_id)
                # Mark accessed in DB for importance tracking
                for r in results:
                    with get_db_context() as db:
                        repo.mark_memory_accessed(db, r.chromadb_id)
                return results
            return []

        async def search_entities():
            if decision.entity:
                return self.entity_store.get_user_entities(user_id)
            return []

        # Latency optimization #1: parallel search
        st_results, lt_results, entity_results = await asyncio.gather(
            search_short_term(),
            search_long_term(),
            search_entities(),
        )

        entity_context = ""
        if decision.entity:
            entity_context = self.entity_store.get_context_string(user_id)

        context = MemoryContext(
            short_term=st_results,
            long_term=lt_results,
            entities=entity_results,
            entity_context_string=entity_context,
            route_decision=decision,
        )

        logger.info(
            "memory_retrieved",
            user_id=user_id,
            short_term_count=len(st_results),
            long_term_count=len(lt_results),
            entity_count=len(entity_results),
            route=f"st={decision.short_term},lt={decision.long_term},ent={decision.entity}",
        )

        return context

    async def store_from_conversation(
        self,
        user_message: str,
        assistant_response: str,
        user_id: str,
        conversation_id: int | None = None,
        message_id: int | None = None,
    ) -> dict:
        """Extract and store memories from a conversation turn.

        This runs as a BACKGROUND TASK after the response is sent.
        """
        results = {"long_term_stored": False, "entities_extracted": 0, "sensitive_redacted": False}

        # Gap #5: Check for sensitive data before storing
        has_sensitive, types = contains_sensitive_data(user_message)
        if has_sensitive:
            user_message = redact_sensitive_data(user_message)
            results["sensitive_redacted"] = True
            logger.info("sensitive_data_redacted", types=types)

        # Store in long-term memory (embed the conversation turn)
        memory_text = f"User said: {user_message}\nAssistant responded: {assistant_response[:200]}"
        chromadb_id = self.long_term.store(
            text=memory_text,
            user_id=user_id,
            conversation_id=conversation_id,
        )

        # Track in metadata table (Gap #8: raw text stored for re-embedding)
        with get_db_context() as db:
            repo.create_memory_metadata(
                db=db,
                user_id=user_id,
                chromadb_id=chromadb_id,
                original_text=memory_text,
                source_conversation_id=conversation_id,
            )
        results["long_term_stored"] = True

        # Extract entities
        conversation_text = f"User: {user_message}\nAssistant: {assistant_response}"
        entities = await self.entity_store.extract_entities(
            conversation_text=conversation_text,
            user_id=user_id,
            conversation_id=conversation_id,
            message_id=message_id,
        )
        results["entities_extracted"] = len(entities)

        logger.info("memory_stored_from_conversation", user_id=user_id, **results)
        return results

    async def forget(self, query: str, user_id: str) -> dict:
        """Forget specific information (Gap #5: user privacy control)."""
        results = {"entities_deleted": 0, "memories_deleted": 0}

        # Delete matching entities
        with get_db_context() as db:
            matching = repo.search_entities(db, user_id, query)
            for entity in matching:
                repo.delete_entity(db, entity.id)
                results["entities_deleted"] += 1

        # Delete matching long-term memories
        all_memories = self.long_term.get_all(user_id)
        for mem in all_memories:
            if query.lower() in mem["text"].lower():
                self.long_term.delete(mem["id"])
                # Also delete metadata
                with get_db_context() as db:
                    db_meta = (
                        db.query(repo.MemoryMetadata)
                        .filter(repo.MemoryMetadata.chromadb_id == mem["id"])
                        .first()
                    )
                    if db_meta:
                        db.delete(db_meta)
                        db.commit()
                results["memories_deleted"] += 1

        # Clear entity cache
        self.entity_store._cache.pop(user_id, None)

        logger.info("memory_forgotten", user_id=user_id, query=query, **results)
        return results

    def prefetch_user(self, user_id: str) -> None:
        """Pre-load user's entity memory into cache.

        Latency optimization #5: called when conversation starts.
        """
        self.entity_store.get_user_entities(user_id)
        logger.debug("user_prefetched", user_id=user_id)

    def add_to_short_term(self, role: str, content: str) -> None:
        self.short_term.add(role, content)

    def clear_short_term(self) -> None:
        self.short_term.clear()
