from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db import repository as repo

router = APIRouter(prefix="/api/conversations", tags=["Conversations"])


@router.get("")
def list_conversations(
    user_id: str = Query("default"),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    convs = repo.get_conversations(db, user_id=user_id, limit=limit)
    return [
        {
            "id": c.id,
            "title": c.title,
            "message_count": c.message_count,
            "is_active": c.is_active,
            "created_at": c.created_at.isoformat() if c.created_at else "",
            "updated_at": c.updated_at.isoformat() if c.updated_at else "",
        }
        for c in convs
    ]


@router.get("/{conversation_id}")
def get_conversation(conversation_id: int, db: Session = Depends(get_db)):
    conv = repo.get_conversation(db, conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    return {
        "id": conv.id,
        "title": conv.title,
        "message_count": conv.message_count,
        "created_at": conv.created_at.isoformat() if conv.created_at else "",
        "messages": [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "created_at": m.created_at.isoformat() if m.created_at else "",
            }
            for m in conv.messages
        ],
    }


@router.delete("/{conversation_id}")
def delete_conversation(conversation_id: int, db: Session = Depends(get_db)):
    success = repo.delete_conversation(db, conversation_id)
    if not success:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"status": "deleted"}


@router.post("")
def create_conversation(
    user_id: str = Query("default"),
    db: Session = Depends(get_db),
):
    conv = repo.create_conversation(db, user_id=user_id)
    return {"id": conv.id, "title": conv.title}
