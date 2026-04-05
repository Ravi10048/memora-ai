from __future__ import annotations

from dataclasses import dataclass, field

from app.config import settings
from app.utils.token_counter import count_tokens, truncate_to_budget


@dataclass
class ShortTermMemory:
    """In-memory sliding window of recent messages in current conversation.

    Analogous to human working memory — holds the immediate conversation context.
    """

    max_messages: int = field(default_factory=lambda: settings.short_term_max_messages)
    _messages: list[dict] = field(default_factory=list)

    def add(self, role: str, content: str) -> None:
        self._messages.append({"role": role, "content": content})
        # Slide the window
        if len(self._messages) > self.max_messages:
            self._messages = self._messages[-self.max_messages:]

    def get_context(self) -> list[dict]:
        """Return messages formatted for LLM context."""
        return list(self._messages)

    def get_context_string(self) -> str:
        """Return messages as a formatted string for embedding in prompts."""
        parts = []
        for msg in self._messages:
            role = msg["role"].capitalize()
            parts.append(f"{role}: {msg['content']}")
        text = "\n".join(parts)
        return truncate_to_budget(text, "short_term")

    def search(self, query: str) -> list[dict]:
        """Return all recent messages (short-term is fully in context)."""
        return self.get_context()

    def clear(self) -> None:
        self._messages.clear()

    def load_from_messages(self, messages: list[dict]) -> None:
        """Load messages from database on conversation resume."""
        self._messages = messages[-self.max_messages:]

    @property
    def size(self) -> int:
        return len(self._messages)

    @property
    def token_count(self) -> int:
        return sum(count_tokens(m["content"]) for m in self._messages)
