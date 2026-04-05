from __future__ import annotations

from app.tools.base import BaseTool, ToolResult
from app.memory.privacy import contains_sensitive_data


class MemorySaveTool(BaseTool):
    """Agent explicitly saves important facts during conversation.

    Letta/MemGPT pattern: agent decides what's worth remembering.
    """

    name = "save_to_memory"
    description = "Save an important fact or preference to remember for future conversations. Use when the user shares personal information you should remember."
    parameters = "The fact to remember, e.g., 'User prefers Python over Java', 'User owns 100 shares of Infosys at 1500'"

    def __init__(self, memory_manager=None):
        self._memory_manager = memory_manager
        self._user_id = "default"

    def set_context(self, memory_manager, user_id: str) -> None:
        self._memory_manager = memory_manager
        self._user_id = user_id

    async def execute(self, input_text: str) -> ToolResult:
        if not self._memory_manager:
            return ToolResult(output="Memory not available", success=False)

        # Gap #5: Check for sensitive data
        has_sensitive, types = contains_sensitive_data(input_text)
        if has_sensitive:
            return ToolResult(
                output=f"Cannot save — contains sensitive data ({', '.join(types)}). "
                       "This information will not be stored for security reasons.",
                success=False,
            )

        # Store in long-term memory
        chromadb_id = self._memory_manager.long_term.store(
            text=input_text,
            user_id=self._user_id,
            importance=0.8,  # Explicitly saved = high importance
        )

        return ToolResult(output=f"Saved to memory: {input_text[:100]}")
