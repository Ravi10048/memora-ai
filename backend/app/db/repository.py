from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Sequence

from sqlalchemy import desc
from sqlalchemy.orm import Session, joinedload

from app.db.models import Conversation, Message, Entity, MemoryMetadata


# ── Conversation Operations ──


def create_conversation(db: Session, user_id: str = "default", title: str = "New Conversation") -> Conversation:
    conv = Conversation(user_id=user_id, title=title)
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return conv


def get_conversation(db: Session, conversation_id: int) -> Conversation | None:
    return (
        db.query(Conversation)
        .options(joinedload(Conversation.messages))
        .filter(Conversation.id == conversation_id)
        .first()
    )


def get_conversations(db: Session, user_id: str = "default", limit: int = 50) -> Sequence[Conversation]:
    return (
        db.query(Conversation)
        .filter(Conversation.user_id == user_id)
        .order_by(desc(Conversation.updated_at))
        .limit(limit)
        .all()
    )


def update_conversation_title(db: Session, conversation_id: int, title: str) -> None:
    conv = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if conv:
        conv.title = title
        conv.updated_at = datetime.now(timezone.utc)
        db.commit()


def delete_conversation(db: Session, conversation_id: int) -> bool:
    conv = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if conv:
        db.delete(conv)
        db.commit()
        return True
    return False


# ── Message Operations ──


def add_message(
    db: Session,
    conversation_id: int,
    role: str,
    content: str,
    metadata: dict | None = None,
    token_count: int = 0,
) -> Message:
    msg = Message(
        conversation_id=conversation_id,
        role=role,
        content=content,
        raw_content=content,
        metadata_json=json.dumps(metadata) if metadata else None,
        token_count=token_count,
    )
    db.add(msg)
    # Update conversation
    conv = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if conv:
        conv.message_count = (conv.message_count or 0) + 1
        conv.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(msg)
    return msg


def get_recent_messages(db: Session, conversation_id: int, limit: int = 20) -> list[Message]:
    return (
        db.query(Message)
        .filter(Message.conversation_id == conversation_id)
        .order_by(desc(Message.created_at))
        .limit(limit)
        .all()
    )[::-1]  # Reverse to chronological order


# ── Entity Operations ──


def create_entity(
    db: Session,
    user_id: str,
    entity_name: str,
    entity_type: str,
    attributes: dict,
    confidence: float = 0.8,
    source_message_id: int | None = None,
    source_conversation_id: int | None = None,
) -> Entity:
    entity = Entity(
        user_id=user_id,
        entity_name=entity_name,
        entity_type=entity_type,
        attributes=json.dumps(attributes),
        confidence=confidence,
        source_message_id=source_message_id,
        source_conversation_id=source_conversation_id,
    )
    db.add(entity)
    db.commit()
    db.refresh(entity)
    return entity


def get_entities(db: Session, user_id: str) -> Sequence[Entity]:
    return (
        db.query(Entity)
        .filter(Entity.user_id == user_id)
        .order_by(desc(Entity.updated_at))
        .all()
    )


def get_entity_by_name(db: Session, user_id: str, entity_name: str) -> Entity | None:
    return (
        db.query(Entity)
        .filter(Entity.user_id == user_id, Entity.entity_name == entity_name)
        .first()
    )


def update_entity(
    db: Session,
    entity_id: int,
    attributes: dict | None = None,
    confidence: float | None = None,
) -> Entity | None:
    entity = db.query(Entity).filter(Entity.id == entity_id).first()
    if not entity:
        return None
    if attributes is not None:
        # Merge attributes (don't overwrite everything)
        existing = json.loads(entity.attributes) if entity.attributes else {}
        existing.update(attributes)
        entity.attributes = json.dumps(existing)
    if confidence is not None:
        entity.confidence = confidence
    entity.updated_at = datetime.now(timezone.utc)
    entity.access_count += 1
    db.commit()
    db.refresh(entity)
    return entity


def delete_entity(db: Session, entity_id: int) -> bool:
    entity = db.query(Entity).filter(Entity.id == entity_id).first()
    if entity:
        db.delete(entity)
        db.commit()
        return True
    return False


def search_entities(db: Session, user_id: str, query: str) -> Sequence[Entity]:
    """Search entities by name (case-insensitive partial match)."""
    return (
        db.query(Entity)
        .filter(
            Entity.user_id == user_id,
            Entity.entity_name.ilike(f"%{query}%"),
        )
        .all()
    )


# ── Memory Metadata Operations ──


def create_memory_metadata(
    db: Session,
    user_id: str,
    chromadb_id: str,
    original_text: str,
    embedding_model: str = "all-MiniLM-L6-v2",
    source_conversation_id: int | None = None,
    importance_score: float = 0.5,
) -> MemoryMetadata:
    meta = MemoryMetadata(
        user_id=user_id,
        chromadb_id=chromadb_id,
        original_text=original_text,
        embedding_model=embedding_model,
        source_conversation_id=source_conversation_id,
        importance_score=importance_score,
    )
    db.add(meta)
    db.commit()
    db.refresh(meta)
    return meta


def get_memory_metadata(db: Session, user_id: str) -> Sequence[MemoryMetadata]:
    return (
        db.query(MemoryMetadata)
        .filter(MemoryMetadata.user_id == user_id, MemoryMetadata.is_consolidated == False)
        .order_by(desc(MemoryMetadata.created_at))
        .all()
    )


def mark_memory_accessed(db: Session, chromadb_id: str) -> None:
    meta = db.query(MemoryMetadata).filter(MemoryMetadata.chromadb_id == chromadb_id).first()
    if meta:
        meta.access_count += 1
        meta.last_accessed_at = datetime.now(timezone.utc)
        db.commit()


def delete_memory_metadata(db: Session, memory_id: int) -> str | None:
    """Delete memory metadata and return chromadb_id for vector deletion."""
    meta = db.query(MemoryMetadata).filter(MemoryMetadata.id == memory_id).first()
    if meta:
        chromadb_id = meta.chromadb_id
        db.delete(meta)
        db.commit()
        return chromadb_id
    return None
