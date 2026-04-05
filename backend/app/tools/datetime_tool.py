from __future__ import annotations

from datetime import datetime, timezone

from app.tools.base import BaseTool, ToolResult


class DateTimeTool(BaseTool):
    name = "datetime"
    description = "Get current date, time, or day of the week. Use when the user asks about today's date or current time."
    parameters = "A query like 'current date', 'current time', 'what day is it'"

    async def execute(self, input_text: str) -> ToolResult:
        now = datetime.now(timezone.utc)
        ist = now.astimezone(tz=None)  # Local timezone

        info = {
            "utc": now.strftime("%Y-%m-%d %H:%M:%S UTC"),
            "local": ist.strftime("%Y-%m-%d %H:%M:%S %Z"),
            "date": ist.strftime("%A, %B %d, %Y"),
            "time": ist.strftime("%I:%M %p"),
            "day": ist.strftime("%A"),
        }

        output = f"Date: {info['date']}\nTime: {info['time']}\nDay: {info['day']}"
        return ToolResult(output=output)
