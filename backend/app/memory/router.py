from __future__ import annotations

import json
from dataclasses import dataclass

from app.llm.base import BaseLLMProvider
from app.utils.logger import get_logger

logger = get_logger(__name__)

ROUTER_PROMPT = """Classify this user message to decide which memory stores to check.

Message: "{query}"
Recent context (last 2 messages): "{recent_context}"

Respond with ONLY valid JSON:
{{"short_term": true/false, "long_term": true/false, "entity": true/false}}

Guidelines:
- short_term: true if the message refers to something said earlier in THIS conversation ("continue", "as I said", "what we were discussing")
- long_term: true if the message asks about PAST conversations or previously shared information ("what did I tell you", "remember when", personal questions)
- entity: true if the message involves facts about the user or known entities ("my job", "where do I work", personal details)
- For greetings ("hello", "hi"), general questions ("what is Python"), or simple tasks: all false
- For "what do you know about me": entity=true, long_term=true"""


@dataclass
class MemoryRouteDecision:
    short_term: bool = True
    long_term: bool = False
    entity: bool = False


class MemoryRouter:
    """Decides which memory stores to query for a given message.

    Latency optimization #2: skip unnecessary memory searches.
    A casual "hello" doesn't need vector search (saves ~400ms).
    """

    def __init__(self, llm: BaseLLMProvider | None = None):
        self.llm = llm

    async def route(self, query: str, recent_context: str = "") -> MemoryRouteDecision:
        """Classify which memory stores are needed."""
        # Fast path: very short messages are usually casual
        lower = query.lower().strip()
        if lower in ("hi", "hello", "hey", "thanks", "ok", "bye", "good morning", "good night"):
            return MemoryRouteDecision(short_term=False, long_term=False, entity=False)

        # Fast path: "what do you know about me" → entity + long-term
        if "know about me" in lower or "remember about me" in lower:
            return MemoryRouteDecision(short_term=False, long_term=True, entity=True)

        # Fast path: "forget" → needs entity lookup
        if lower.startswith("forget "):
            return MemoryRouteDecision(short_term=False, long_term=True, entity=True)

        if not self.llm:
            # No LLM available — default to checking all
            return MemoryRouteDecision(short_term=True, long_term=True, entity=True)

        try:
            prompt = ROUTER_PROMPT.format(query=query, recent_context=recent_context[:500])
            response = await self.llm.generate(
                prompt=prompt,
                system_prompt="You classify memory routing decisions. Return only JSON.",
                temperature=0.0,
                max_tokens=100,
                response_format={"type": "json_object"},
            )

            data = json.loads(response.content)
            decision = MemoryRouteDecision(
                short_term=data.get("short_term", True),
                long_term=data.get("long_term", False),
                entity=data.get("entity", False),
            )

            logger.debug(
                "memory_routed",
                query_preview=query[:50],
                short_term=decision.short_term,
                long_term=decision.long_term,
                entity=decision.entity,
            )
            return decision

        except Exception as e:
            logger.warning("memory_router_failed", error=str(e))
            # Fallback: check everything
            return MemoryRouteDecision(short_term=True, long_term=True, entity=True)
