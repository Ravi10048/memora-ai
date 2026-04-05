from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class ToolResult:
    output: str
    success: bool = True
    error: str = ""


class BaseTool(ABC):
    """Abstract base class for all agent tools."""

    @property
    @abstractmethod
    def name(self) -> str:
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        ...

    @property
    @abstractmethod
    def parameters(self) -> str:
        """Describe expected input for the LLM."""
        ...

    @abstractmethod
    async def execute(self, input_text: str) -> ToolResult:
        ...

    def to_prompt(self) -> str:
        """Format tool for inclusion in system prompt."""
        return f"- {self.name}: {self.description} | Input: {self.parameters}"
