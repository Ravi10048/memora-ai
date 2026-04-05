from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from app.tools.base import BaseTool, ToolResult


class CodeExecutorTool(BaseTool):
    name = "run_python"
    description = "Execute Python code in a sandboxed environment. Use for data processing, calculations, or testing code snippets."
    parameters = "Python code to execute, e.g., 'print(sorted([3,1,2]))'"

    TIMEOUT = 10  # seconds
    MAX_OUTPUT = 2000  # characters

    async def execute(self, input_text: str) -> ToolResult:
        try:
            # Write code to temp file
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".py", delete=False
            ) as f:
                f.write(input_text)
                temp_path = f.name

            # Execute with timeout
            result = subprocess.run(
                ["python3", temp_path],
                capture_output=True,
                text=True,
                timeout=self.TIMEOUT,
                cwd=tempfile.gettempdir(),
            )

            # Cleanup
            Path(temp_path).unlink(missing_ok=True)

            output = result.stdout[:self.MAX_OUTPUT]
            if result.stderr:
                error = result.stderr[:self.MAX_OUTPUT]
                if result.returncode != 0:
                    return ToolResult(output=output, success=False, error=error)
                output += f"\n[stderr]: {error}"

            return ToolResult(output=output or "(no output)")

        except subprocess.TimeoutExpired:
            Path(temp_path).unlink(missing_ok=True)
            return ToolResult(output="", success=False, error=f"Code execution timed out after {self.TIMEOUT}s")
        except Exception as e:
            return ToolResult(output="", success=False, error=f"Execution failed: {str(e)}")
