from __future__ import annotations

import ast
import operator

from app.tools.base import BaseTool, ToolResult

# Safe operators for math evaluation
SAFE_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def safe_eval(expr: str) -> float:
    """Safely evaluate a math expression using AST parsing."""
    tree = ast.parse(expr, mode="eval")

    def _eval(node):
        if isinstance(node, ast.Expression):
            return _eval(node.body)
        elif isinstance(node, ast.Constant):
            if isinstance(node.value, (int, float)):
                return node.value
            raise ValueError(f"Unsupported constant: {node.value}")
        elif isinstance(node, ast.BinOp):
            op = SAFE_OPERATORS.get(type(node.op))
            if not op:
                raise ValueError(f"Unsupported operator: {type(node.op).__name__}")
            return op(_eval(node.left), _eval(node.right))
        elif isinstance(node, ast.UnaryOp):
            op = SAFE_OPERATORS.get(type(node.op))
            if not op:
                raise ValueError(f"Unsupported operator: {type(node.op).__name__}")
            return op(_eval(node.operand))
        else:
            raise ValueError(f"Unsupported expression: {type(node).__name__}")

    return _eval(tree)


class CalculatorTool(BaseTool):
    name = "calculator"
    description = "Perform mathematical calculations. Supports +, -, *, /, **, %, //."
    parameters = "A math expression, e.g., '(1580.25 - 1500) * 100'"

    async def execute(self, input_text: str) -> ToolResult:
        try:
            result = safe_eval(input_text.strip())
            return ToolResult(output=str(result))
        except ZeroDivisionError:
            return ToolResult(output="", success=False, error="Division by zero")
        except Exception as e:
            return ToolResult(output="", success=False, error=f"Invalid expression: {str(e)}")
