from __future__ import annotations

from app.tools.base import BaseTool, ToolResult


class WebSearchTool(BaseTool):
    name = "web_search"
    description = "Search the web for current information. Use for real-time data like stock prices, news, weather, or facts you don't know."
    parameters = "A search query string, e.g., 'Infosys stock price today'"

    async def execute(self, input_text: str) -> ToolResult:
        try:
            from duckduckgo_search import DDGS

            with DDGS() as ddgs:
                results = list(ddgs.text(input_text, max_results=3))

            if not results:
                return ToolResult(output="No search results found.", success=True)

            formatted = []
            for r in results:
                title = r.get("title", "")
                body = r.get("body", "")
                formatted.append(f"**{title}**: {body}")

            return ToolResult(output="\n\n".join(formatted))

        except Exception as e:
            return ToolResult(output="", success=False, error=f"Search failed: {str(e)}")
