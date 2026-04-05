from __future__ import annotations

from app.tools.base import BaseTool, ToolResult


class MemorySearchTool(BaseTool):
    """Agent explicitly searches its own memory during ReAct loop.

    Letta/MemGPT pattern: memory as tool, not just pre-fetch.
    This is in ADDITION to automatic memory retrieval before the loop.
    """

    name = "search_memory"
    description = "Search your memory for information about the user or past conversations. Use when you need to recall specific details."
    parameters = "A search query about the user or past conversations, e.g., 'user stock holdings', 'previous career discussion'"

    def __init__(self, memory_manager=None):
        self._memory_manager = memory_manager
        self._user_id = "default"

    def set_context(self, memory_manager, user_id: str) -> None:
        self._memory_manager = memory_manager
        self._user_id = user_id

    async def execute(self, input_text: str) -> ToolResult:
        if not self._memory_manager:
            return ToolResult(output="Memory not available", success=False)

        # Search long-term
        lt_results = self._memory_manager.long_term.search(input_text, self._user_id)
        # Search entities
        entity_results = self._memory_manager.entity_store.search(input_text, self._user_id)

        parts = []
        if lt_results:
            parts.append("From past conversations:")
            for r in lt_results[:3]:
                parts.append(f"  - {r.text} (relevance: {r.final_score:.2f})")

        if entity_results:
            parts.append("Known facts:")
            for e in entity_results[:5]:
                attrs = ", ".join(f"{k}: {v}" for k, v in e["attributes"].items())
                parts.append(f"  - {e['name']} ({e['type']}): {attrs}")

        if not parts:
            return ToolResult(output="No relevant memories found.")

        return ToolResult(output="\n".join(parts))
