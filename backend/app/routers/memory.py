from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db import repository as repo
from app.memory.long_term import LongTermMemory

router = APIRouter(prefix="/api/memory", tags=["Memory"])


# ── Entity Memory ──


@router.get("/entities")
def list_entities(user_id: str = Query("default"), db: Session = Depends(get_db)):
    entities = repo.get_entities(db, user_id)
    return [
        {
            "id": e.id,
            "name": e.entity_name,
            "type": e.entity_type,
            "attributes": json.loads(e.attributes) if e.attributes else {},
            "confidence": e.confidence,
            "access_count": e.access_count,
            "created_at": e.created_at.isoformat() if e.created_at else "",
            "updated_at": e.updated_at.isoformat() if e.updated_at else "",
        }
        for e in entities
    ]


class EntityUpdateRequest(BaseModel):
    attributes: dict | None = None
    confidence: float | None = None


@router.put("/entities/{entity_id}")
def update_entity(
    entity_id: int,
    request: EntityUpdateRequest,
    db: Session = Depends(get_db),
):
    entity = repo.update_entity(db, entity_id, request.attributes, request.confidence)
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")
    return {"status": "updated", "id": entity.id}


@router.delete("/entities/{entity_id}")
def delete_entity(entity_id: int, db: Session = Depends(get_db)):
    success = repo.delete_entity(db, entity_id)
    if not success:
        raise HTTPException(status_code=404, detail="Entity not found")
    return {"status": "deleted"}


# ── Long-term Memory ──


@router.get("/long-term")
def list_long_term_memories(user_id: str = Query("default"), db: Session = Depends(get_db)):
    metas = repo.get_memory_metadata(db, user_id)
    return [
        {
            "id": m.id,
            "chromadb_id": m.chromadb_id,
            "text": m.original_text,
            "importance": m.importance_score,
            "access_count": m.access_count,
            "last_accessed": m.last_accessed_at.isoformat() if m.last_accessed_at else None,
            "created_at": m.created_at.isoformat() if m.created_at else "",
        }
        for m in metas
    ]


@router.delete("/long-term/{memory_id}")
def delete_long_term_memory(memory_id: int, db: Session = Depends(get_db)):
    chromadb_id = repo.delete_memory_metadata(db, memory_id)
    if not chromadb_id:
        raise HTTPException(status_code=404, detail="Memory not found")

    # Also delete from ChromaDB
    long_term = LongTermMemory()
    long_term.delete(chromadb_id)

    return {"status": "deleted"}


# ── Search Across All Memory ──


class MemorySearchRequest(BaseModel):
    query: str
    user_id: str = "default"


@router.post("/search")
def search_memory(request: MemorySearchRequest, db: Session = Depends(get_db)):
    long_term = LongTermMemory()

    # Search long-term
    lt_results = long_term.search(request.query, request.user_id)

    # Search entities
    entity_results = repo.search_entities(db, request.user_id, request.query)

    return {
        "long_term": [
            {
                "text": r.text,
                "score": r.final_score,
                "similarity": r.similarity,
                "recency": r.recency_score,
                "created_at": r.created_at,
            }
            for r in lt_results
        ],
        "entities": [
            {
                "id": e.id,
                "name": e.entity_name,
                "type": e.entity_type,
                "attributes": json.loads(e.attributes) if e.attributes else {},
            }
            for e in entity_results
        ],
    }


# ── Forget ──


class ForgetRequest(BaseModel):
    query: str
    user_id: str = "default"


@router.post("/forget")
async def forget_memory(request: ForgetRequest, db: Session = Depends(get_db)):
    from app.memory.manager import MemoryManager

    memory = MemoryManager()
    result = await memory.forget(request.query, request.user_id)
    return result
