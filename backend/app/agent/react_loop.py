from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import AsyncGenerator

from app.agent.prompts import SYSTEM_PROMPT, REACT_TEMPLATE, CONVERSATION_TITLE_PROMPT
from app.agent.validator import ResponseValidator
from app.llm.base import BaseLLMProvider
from app.llm.factory import get_llm_provider
from app.memory.manager import MemoryManager
from app.tools.registry import ToolRegistry
from app.tools.base import ToolResult
from app.tools.web_search import WebSearchTool
from app.tools.calculator import CalculatorTool
from app.tools.code_executor import CodeExecutorTool
from app.tools.datetime_tool import DateTimeTool
from app.tools.memory_search import MemorySearchTool
from app.tools.memory_save import MemorySaveTool
from app.utils.logger import get_logger

logger = get_logger(__name__)

MAX_ITERATIONS = 5


@dataclass
class AgentStep:
    """A single step in the ReAct loop — streamed to frontend."""
    type: str  # "thinking", "tool_call", "tool_result", "memory_read", "memory_write", "self_check", "token", "done", "error"
    content: str = ""
    tool: str = ""
    store: str = ""
    confident: bool = True
    metadata: dict = field(default_factory=dict)


class ReActAgent:
    """ReAct reasoning agent with memory and tool-use.

    Flow:
        1. Retrieve memory context (parallel search)
        2. Build prompt with memory + tools + conversation
        3. ReAct loop: Think → Act → Observe (max 5 iterations)
        4. Validate response (self-correction)
        5. Stream thinking steps + final answer to frontend
        6. Store new memories in background
    """

    def __init__(
        self,
        llm: BaseLLMProvider | None = None,
        memory_manager: MemoryManager | None = None,
        user_id: str = "default",
    ):
        self.llm = llm or get_llm_provider()
        self.memory = memory_manager or MemoryManager(llm=self.llm)
        self.user_id = user_id
        self.validator = ResponseValidator(self.llm)

        # Set up tools
        self.tool_registry = ToolRegistry()
        self._register_tools()

    def _register_tools(self) -> None:
        self.tool_registry.register(WebSearchTool())
        self.tool_registry.register(CalculatorTool())
        self.tool_registry.register(CodeExecutorTool())
        self.tool_registry.register(DateTimeTool())

        # Memory tools (Letta pattern)
        mem_search = MemorySearchTool()
        mem_search.set_context(self.memory, self.user_id)
        self.tool_registry.register(mem_search)

        mem_save = MemorySaveTool()
        mem_save.set_context(self.memory, self.user_id)
        self.tool_registry.register(mem_save)

    async def process_message(
        self,
        user_message: str,
        conversation_id: int | None = None,
    ) -> AsyncGenerator[AgentStep, None]:
        """Process a user message through the full ReAct pipeline.

        Yields AgentStep events for real-time streaming to frontend.
        """
        # Step 1: Add to short-term memory
        self.memory.add_to_short_term("user", user_message)

        # Step 2: Retrieve memory context (parallel search)
        yield AgentStep(type="thinking", content="Searching memory for relevant context...")

        memory_context = await self.memory.retrieve(user_message, self.user_id)

        # Emit memory reads
        if memory_context.long_term:
            yield AgentStep(
                type="memory_read",
                store="long_term",
                content=f"Found {len(memory_context.long_term)} relevant past memories",
                metadata={"results": [r.text[:100] for r in memory_context.long_term]},
            )
        if memory_context.entities:
            yield AgentStep(
                type="memory_read",
                store="entity",
                content=f"Found {len(memory_context.entities)} known entities",
                metadata={"entities": [e["name"] for e in memory_context.entities]},
            )

        # Step 3: Build prompt
        tools_prompt = self.tool_registry.get_tools_prompt()
        memory_prompt_context = memory_context.to_prompt_context()

        system_prompt = SYSTEM_PROMPT.format(
            tools_prompt=tools_prompt,
            memory_context=memory_prompt_context or "No relevant memories found.",
        )

        # Build conversation history from short-term
        conv_history = self.memory.short_term.get_context_string()

        full_prompt = REACT_TEMPLATE.format(
            system_prompt=system_prompt,
            conversation_history=conv_history,
            user_message=user_message,
        )

        # Step 4: ReAct loop
        final_answer = ""
        context_so_far = full_prompt

        for iteration in range(MAX_ITERATIONS):
            response = await self.llm.generate(
                prompt=context_so_far,
                temperature=0.3,
                max_tokens=2048,
            )

            text = response.content.strip()

            # Parse the response for THOUGHT, ACTION, FINAL ANSWER
            thought, action, action_input, answer = self._parse_react_output(text)

            if thought:
                yield AgentStep(type="thinking", content=thought)

            if answer:
                final_answer = answer
                break

            if action:
                yield AgentStep(type="tool_call", tool=action, content=action_input)

                # Execute tool
                result = await self.tool_registry.execute(action, action_input)

                yield AgentStep(
                    type="tool_result",
                    tool=action,
                    content=result.output if result.success else f"Error: {result.error}",
                )

                # Add to context for next iteration
                context_so_far += f"\n{text}\nOBSERVATION: {result.output}\n\nContinue reasoning. Start with THOUGHT:"
            else:
                # No action and no final answer — treat as final answer
                final_answer = text
                break

        if not final_answer:
            final_answer = "I wasn't able to complete my reasoning. Could you rephrase your question?"

        # Step 5: Self-correction
        yield AgentStep(type="self_check", content="Validating response...")

        is_valid, corrected_response, confidence = await self.validator.validate(
            user_message=user_message,
            response=final_answer,
            memory_context=memory_prompt_context,
        )

        yield AgentStep(
            type="self_check",
            confident=is_valid,
            content=f"Confidence: {int(confidence * 100)}%",
            metadata={"corrected": not is_valid},
        )

        final_response = corrected_response if not is_valid else final_answer

        # Step 6: Stream final answer token by token
        words = final_response.split(" ")
        for word in words:
            yield AgentStep(type="token", content=word + " ")

        # Step 7: Add assistant response to short-term
        self.memory.add_to_short_term("assistant", final_response)

        # Step 8: Store memories in background (don't block)
        yield AgentStep(type="memory_write", content="Saving to memory...")

        yield AgentStep(
            type="done",
            content=final_response,
            metadata={
                "conversation_id": conversation_id,
                "tokens_used": 0,
            },
        )

    async def generate_title(self, first_message: str) -> str:
        """Generate a short conversation title from the first message."""
        try:
            prompt = CONVERSATION_TITLE_PROMPT.format(message=first_message)
            response = await self.llm.generate(prompt=prompt, temperature=0.5, max_tokens=20)
            return response.content.strip()[:50]
        except Exception:
            return first_message[:40]

    def _parse_react_output(self, text: str) -> tuple[str, str, str, str]:
        """Parse ReAct-formatted output into components.

        Returns: (thought, action, action_input, final_answer)
        """
        thought = ""
        action = ""
        action_input = ""
        final_answer = ""

        # Extract THOUGHT
        thought_match = re.search(r"THOUGHT:\s*(.+?)(?=ACTION:|FINAL ANSWER:|$)", text, re.DOTALL)
        if thought_match:
            thought = thought_match.group(1).strip()

        # Extract FINAL ANSWER
        answer_match = re.search(r"FINAL ANSWER:\s*(.+?)$", text, re.DOTALL)
        if answer_match:
            final_answer = answer_match.group(1).strip()
            return thought, "", "", final_answer

        # Extract ACTION and INPUT
        action_match = re.search(r"ACTION:\s*(\w+)", text)
        input_match = re.search(r"INPUT:\s*(.+?)(?=THOUGHT:|ACTION:|FINAL ANSWER:|$)", text, re.DOTALL)

        if action_match:
            action = action_match.group(1).strip()
        if input_match:
            action_input = input_match.group(1).strip()

        return thought, action, action_input, final_answer
