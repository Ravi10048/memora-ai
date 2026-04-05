from __future__ import annotations

from app.llm.base import BaseLLMProvider
from app.utils.logger import get_logger

logger = get_logger(__name__)

VALIDATION_PROMPT = """Review this response for accuracy before sending to the user.

User asked: {user_message}
Proposed response: {response}
Memory context used: {memory_context}

Check:
1. Does the response only state facts from memory or tool results? (no hallucination)
2. Is the response relevant to the user's question?
3. Are calculations correct?

Respond with ONLY JSON:
{{"is_valid": true/false, "confidence": 0.0-1.0, "issues": ["issue1", ...], "corrected_response": "..." or null}}

If valid, set corrected_response to null. If invalid, provide the corrected version."""


class ResponseValidator:
    """Validates agent responses before sending to user.

    Self-correction: catches hallucinations, wrong calculations, irrelevant answers.
    Only triggered for responses that reference memory or tool results.
    """

    def __init__(self, llm: BaseLLMProvider):
        self.llm = llm

    async def validate(
        self,
        user_message: str,
        response: str,
        memory_context: str = "",
    ) -> tuple[bool, str, float]:
        """Validate a response.

        Returns: (is_valid, final_response, confidence)
        """
        # Skip validation for simple responses (no memory/tool refs)
        if len(response) < 50 and not memory_context:
            return True, response, 0.95

        try:
            prompt = VALIDATION_PROMPT.format(
                user_message=user_message,
                response=response[:1000],
                memory_context=memory_context[:500],
            )

            result = await self.llm.generate(
                prompt=prompt,
                system_prompt="You validate AI responses for accuracy.",
                temperature=0.0,
                max_tokens=1024,
                response_format={"type": "json_object"},
            )

            import json
            data = json.loads(result.content)
            is_valid = data.get("is_valid", True)
            confidence = data.get("confidence", 0.8)
            corrected = data.get("corrected_response")

            if not is_valid and corrected:
                logger.info(
                    "response_corrected",
                    issues=data.get("issues", []),
                    confidence=confidence,
                )
                return False, corrected, confidence

            return is_valid, response, confidence

        except Exception as e:
            logger.warning("validation_failed", error=str(e))
            # If validation fails, send original response
            return True, response, 0.7
