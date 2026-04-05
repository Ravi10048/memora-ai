from __future__ import annotations


class AppError(Exception):
    def __init__(self, message: str, status_code: int = 500):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class LLMProviderError(AppError):
    def __init__(self, message: str = "LLM provider error"):
        super().__init__(message, status_code=502)


class MemoryError(AppError):
    def __init__(self, message: str = "Memory operation failed"):
        super().__init__(message, status_code=500)


class ToolError(AppError):
    def __init__(self, message: str = "Tool execution failed"):
        super().__init__(message, status_code=500)


class RateLimitError(AppError):
    def __init__(self, message: str = "Rate limit exceeded", retry_after: int = 60):
        self.retry_after = retry_after
        super().__init__(message, status_code=429)
