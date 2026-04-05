from __future__ import annotations

import json
from functools import lru_cache

from app.config import settings
from app.db.database import get_db_context
from app.db import repository as repo
from app.llm.base import BaseLLMProvider
from app.utils.logger import get_logger

logger = get_logger(__name__)

ENTITY_EXTRACTION_PROMPT = """Extract structured facts from this conversation. Return a JSON array of entities.

Each entity should have:
- entity_name: the name of the person, organization, or concept
- entity_type: one of "person", "organization", "preference", "fact", "location", "project"
- attributes: key-value pairs of facts about this entity

RULES:
- Only extract facts EXPLICITLY stated. Never infer or guess.
- Distinguish between facts about the USER vs facts about OTHER people they mention.
- If user says "My friend Amit works at Google", extract entity for Amit, NOT the user.
- If user says "I work at BlackNGreen", extract entity for the user.

Conversation:
{conversation}

Return ONLY valid JSON array. If no entities found, return [].
Example: [{"entity_name": "User", "entity_type": "person", "attributes": {"company": "BlackNGreen", "role": "AI Engineer"}}]"""


CONFLICT_CHECK_PROMPT = """Two facts about the same entity may conflict. Determine if they do.

Entity: {entity_name}
Existing fact: {existing}
New fact: {new_fact}

Is this a contradiction? Respond with ONLY valid JSON:
{{"is_conflict": true/false, "is_explicit": true/false, "resolution": "keep_new" | "keep_old" | "keep_both", "reason": "brief explanation"}}

- is_explicit: true if the new fact directly overrides (e.g., "I'm no longer vegetarian")
- is_explicit: false if the conflict is indirect (e.g., "I had chicken" vs "I'm vegetarian")"""


class EntityStore:
    """Manages entity memory — structured facts about users and topics.

    Handles:
        - Extraction: LLM pulls entities from conversation
        - Conflict resolution: detects contradictions (Gap #4)
        - CRUD: create, read, update, delete entities
        - LRU Cache: frequently accessed entities cached in RAM (Latency optimization #4)
    """

    # In-memory LRU cache for hot entities
    _cache: dict[str, list[dict]] = {}

    def __init__(self, llm: BaseLLMProvider | None = None):
        self.llm = llm

    async def extract_entities(
        self,
        conversation_text: str,
        user_id: str,
        conversation_id: int | None = None,
        message_id: int | None = None,
    ) -> list[dict]:
        """Extract entities from conversation text using LLM."""
        if not self.llm:
            return []

        prompt = ENTITY_EXTRACTION_PROMPT.format(conversation=conversation_text)

        try:
            response = await self.llm.generate(
                prompt=prompt,
                system_prompt="You are an entity extraction system. Return only valid JSON.",
                temperature=0.1,
                max_tokens=2048,
                response_format={"type": "json_object"},
            )

            entities = self._parse_entities(response.content)

            # Store each entity
            saved = []
            for entity_data in entities:
                entity_name = entity_data.get("entity_name", "")
                entity_type = entity_data.get("entity_type", "fact")
                attributes = entity_data.get("attributes", {})

                if not entity_name:
                    continue

                result = await self._upsert_entity(
                    user_id=user_id,
                    entity_name=entity_name,
                    entity_type=entity_type,
                    attributes=attributes,
                    conversation_id=conversation_id,
                    message_id=message_id,
                )
                if result:
                    saved.append(result)

            # Invalidate cache for this user
            self._cache.pop(user_id, None)

            logger.info("entities_extracted", user_id=user_id, count=len(saved))
            return saved

        except Exception as e:
            logger.error("entity_extraction_failed", error=str(e))
            return []

    async def _upsert_entity(
        self,
        user_id: str,
        entity_name: str,
        entity_type: str,
        attributes: dict,
        conversation_id: int | None = None,
        message_id: int | None = None,
    ) -> dict | None:
        """Create or update an entity, handling conflicts (Gap #4)."""
        with get_db_context() as db:
            existing = repo.get_entity_by_name(db, user_id, entity_name)

            if existing:
                # Check for conflicts
                existing_attrs = json.loads(existing.attributes) if existing.attributes else {}
                has_conflict = False

                for key, new_val in attributes.items():
                    old_val = existing_attrs.get(key)
                    if old_val and old_val != new_val:
                        has_conflict = True
                        logger.info(
                            "entity_conflict_detected",
                            entity=entity_name,
                            field=key,
                            old_value=old_val,
                            new_value=new_val,
                        )

                # For now: merge (new values overwrite old for same keys)
                # Gap #4: In production, use LLM to resolve conflicts
                updated = repo.update_entity(db, existing.id, attributes=attributes)
                if updated:
                    return {
                        "id": updated.id,
                        "name": entity_name,
                        "type": entity_type,
                        "attributes": json.loads(updated.attributes),
                        "action": "updated",
                        "had_conflict": has_conflict,
                    }
            else:
                entity = repo.create_entity(
                    db=db,
                    user_id=user_id,
                    entity_name=entity_name,
                    entity_type=entity_type,
                    attributes=attributes,
                    confidence=0.85,
                    source_message_id=message_id,
                    source_conversation_id=conversation_id,
                )
                return {
                    "id": entity.id,
                    "name": entity_name,
                    "type": entity_type,
                    "attributes": attributes,
                    "action": "created",
                    "had_conflict": False,
                }

        return None

    def get_user_entities(self, user_id: str) -> list[dict]:
        """Get all entities for a user. Uses LRU cache."""
        if user_id in self._cache:
            return self._cache[user_id]

        with get_db_context() as db:
            entities = repo.get_entities(db, user_id)
            result = [
                {
                    "id": e.id,
                    "name": e.entity_name,
                    "type": e.entity_type,
                    "attributes": json.loads(e.attributes) if e.attributes else {},
                    "confidence": e.confidence,
                    "created_at": e.created_at.isoformat() if e.created_at else "",
                    "updated_at": e.updated_at.isoformat() if e.updated_at else "",
                }
                for e in entities
            ]

        # Cache (simple LRU — evict after 100 users)
        if len(self._cache) > 100:
            oldest_key = next(iter(self._cache))
            del self._cache[oldest_key]
        self._cache[user_id] = result

        return result

    def get_context_string(self, user_id: str) -> str:
        """Format entities as context string for LLM prompt."""
        entities = self.get_user_entities(user_id)
        if not entities:
            return "No known facts about this user."

        parts = []
        for e in entities:
            attrs = ", ".join(f"{k}: {v}" for k, v in e["attributes"].items())
            parts.append(f"- {e['name']} ({e['type']}): {attrs}")

        return "Known facts:\n" + "\n".join(parts)

    def search(self, query: str, user_id: str) -> list[dict]:
        """Search entities by name match."""
        with get_db_context() as db:
            results = repo.search_entities(db, user_id, query)
            return [
                {
                    "id": e.id,
                    "name": e.entity_name,
                    "type": e.entity_type,
                    "attributes": json.loads(e.attributes) if e.attributes else {},
                    "confidence": e.confidence,
                }
                for e in results
            ]

    def _parse_entities(self, content: str) -> list[dict]:
        """Parse LLM response into entity list."""
        content = content.strip()
        if content.startswith("```"):
            lines = content.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            content = "\n".join(lines)

        try:
            data = json.loads(content)
            if isinstance(data, list):
                return data
            if isinstance(data, dict) and "entities" in data:
                return data["entities"]
            return [data] if isinstance(data, dict) else []
        except json.JSONDecodeError:
            logger.warning("entity_json_parse_failed", content_preview=content[:200])
            return []
