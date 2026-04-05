from __future__ import annotations


# Approximate token counting (4 chars ≈ 1 token for English text)
def count_tokens(text: str) -> int:
    return len(text) // 4 + 1


# Token budget allocation for context window
TOKEN_BUDGET = {
    "system_prompt": 1500,
    "entity_memory": 500,
    "short_term": 3000,
    "long_term": 2000,
    "tools": 1000,
    "user_query": 500,
    "response_space": 4000,
}
MAX_TOTAL = sum(TOKEN_BUDGET.values())  # ~12500


def truncate_to_budget(text: str, budget_key: str) -> str:
    """Truncate text to fit within its token budget."""
    max_tokens = TOKEN_BUDGET.get(budget_key, 2000)
    max_chars = max_tokens * 4
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n... (truncated)"


def fits_budget(texts: dict[str, str]) -> bool:
    """Check if all texts fit within total budget."""
    total = sum(count_tokens(t) for t in texts.values())
    return total <= MAX_TOTAL
