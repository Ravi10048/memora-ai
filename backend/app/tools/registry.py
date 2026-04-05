from __future__ import annotations

from app.tools.base import BaseTool, ToolResult
from app.utils.logger import get_logger

logger = get_logger(__name__)


class ToolRegistry:
    """Registry of available tools for the agent."""

    def __init__(self):
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        self._tools[tool.name] = tool
        logger.debug("tool_registered", tool=tool.name)

    def get_tool(self, name: str) -> BaseTool | None:
        return self._tools.get(name)

    async def execute(self, tool_name: str, input_text: str) -> ToolResult:
        tool = self.get_tool(tool_name)
        if not tool:
            return ToolResult(output="", success=False, error=f"Unknown tool: {tool_name}")

        try:
            result = await tool.execute(input_text)
            logger.info("tool_executed", tool=tool_name, success=result.success)
            return result
        except Exception as e:
            logger.error("tool_execution_failed", tool=tool_name, error=str(e))
            return ToolResult(output="", success=False, error=str(e))

    def list_tools(self) -> list[str]:
        return list(self._tools.keys())

    def get_tools_prompt(self) -> str:
        """Format all tools for inclusion in system prompt."""
        if not self._tools:
            return "No tools available."
        return "Available tools:\n" + "\n".join(
            tool.to_prompt() for tool in self._tools.values()
        )
