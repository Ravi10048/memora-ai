from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse
from sqlalchemy.orm import Session

from app.agent.react_loop import ReActAgent
from app.db.database import get_db
from app.db import repository as repo
from app.llm.factory import get_llm_provider
from app.memory.manager import MemoryManager
from app.memory.privacy import is_forget_command
from app.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/chat", tags=["Chat"])


class ChatRequest(BaseModel):
    message: str
    conversation_id: int | None = None
    user_id: str = "default"


@router.post("")
async def chat(request: ChatRequest, db: Session = Depends(get_db)):
    """SSE streaming chat endpoint.

    Streams AgentStep events in real-time:
        - thinking: agent's reasoning
        - memory_read: memory search results
        - tool_call: tool invocation
        - tool_result: tool output
        - self_check: validation result
        - token: response word
        - memory_write: background save
        - done: final response with metadata
    """
    user_id = request.user_id
    message = request.message

    # Get or create conversation
    if request.conversation_id:
        conversation_id = request.conversation_id
    else:
        conv = repo.create_conversation(db, user_id=user_id)
        conversation_id = conv.id

    # Save user message to DB
    user_msg = repo.add_message(db, conversation_id, "user", message)

    async def event_generator():
        try:
            llm = get_llm_provider()
            memory = MemoryManager(llm=llm)

            # Latency optimization #5: Pre-fetch user entities
            memory.prefetch_user(user_id)

            # Load short-term from DB (conversation continuity)
            recent = repo.get_recent_messages(db, conversation_id, limit=20)
            for msg in recent[:-1]:  # Exclude the message we just added
                memory.add_to_short_term(msg.role, msg.content)

            # Check for special commands
            is_forget, forget_target = is_forget_command(message)
            if is_forget:
                result = await memory.forget(forget_target, user_id)
                yield {
                    "event": "message",
                    "data": json.dumps({
                        "type": "token",
                        "content": f"Done. I've forgotten information about '{forget_target}'. "
                                   f"Deleted {result['entities_deleted']} entities and "
                                   f"{result['memories_deleted']} memories.",
                    }),
                }
                yield {
                    "event": "message",
                    "data": json.dumps({"type": "done", "content": ""}),
                }
                return

            # Run the ReAct agent
            agent = ReActAgent(llm=llm, memory_manager=memory, user_id=user_id)

            full_response = ""

            async for step in agent.process_message(message, conversation_id):
                yield {
                    "event": "message",
                    "data": json.dumps({
                        "type": step.type,
                        "content": step.content,
                        "tool": step.tool,
                        "store": step.store,
                        "confident": step.confident,
                        "metadata": step.metadata,
                    }),
                }

                if step.type == "done":
                    full_response = step.content

            # Save assistant response to DB
            if full_response:
                repo.add_message(db, conversation_id, "assistant", full_response)

                # Generate conversation title from first message
                conv = repo.get_conversation(db, conversation_id)
                if conv and conv.message_count <= 2:
                    title = await agent.generate_title(message)
                    repo.update_conversation_title(db, conversation_id, title)

            # Background: store memories (non-blocking)
            if full_response:
                asyncio.create_task(
                    memory.store_from_conversation(
                        user_message=message,
                        assistant_response=full_response,
                        user_id=user_id,
                        conversation_id=conversation_id,
                        message_id=user_msg.id,
                    )
                )

        except Exception as e:
            logger.error("chat_error", error=str(e), user_id=user_id)
            yield {
                "event": "message",
                "data": json.dumps({
                    "type": "error",
                    "content": f"An error occurred: {str(e)}",
                }),
            }

    return EventSourceResponse(event_generator())
