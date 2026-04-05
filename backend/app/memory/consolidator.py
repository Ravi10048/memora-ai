from __future__ import annotations

import math
from datetime import datetime, timezone, timedelta

from app.db.database import get_db_context
from app.db.models import MemoryMetadata, Entity
from app.memory.long_term import LongTermMemory
from app.utils.logger import get_logger

logger = get_logger(__name__)


class MemoryConsolidator:
    """Manages memory lifecycle: decay, deduplication, cleanup.

    Gap #2: Memory grows forever → this handles consolidation.

    Runs periodically (can be triggered via API or background job):
        1. Decay: reduce importance of old, unused memories
        2. Cleanup: delete memories below importance threshold
        3. (Future) Merge: combine similar memories
    """

    DECAY_RATE = 0.005  # Per hour — slower than retrieval decay
    MIN_IMPORTANCE = 0.1  # Below this → candidate for deletion
    STALE_DAYS = 60  # Memories untouched for 60 days → delete

    def __init__(self, long_term: LongTermMemory):
        self.long_term = long_term

    def run_consolidation(self, user_id: str) -> dict:
        """Run full consolidation cycle for a user."""
        stats = {"decayed": 0, "deleted": 0}

        with get_db_context() as db:
            metas = (
                db.query(MemoryMetadata)
                .filter(MemoryMetadata.user_id == user_id)
                .all()
            )

            now = datetime.now(timezone.utc)
            stale_cutoff = now - timedelta(days=self.STALE_DAYS)

            for meta in metas:
                # Apply decay based on time since last access
                last_access = meta.last_accessed_at or meta.created_at
                if last_access.tzinfo is None:
                    last_access = last_access.replace(tzinfo=timezone.utc)
                hours_since = (now - last_access).total_seconds() / 3600
                decay = math.exp(-self.DECAY_RATE * hours_since)
                new_importance = meta.importance_score * decay

                # Boost for frequently accessed memories
                access_boost = min(meta.access_count * 0.05, 0.3)
                new_importance = min(new_importance + access_boost, 1.0)

                # Delete if stale and unimportant
                if new_importance < self.MIN_IMPORTANCE and meta.created_at < stale_cutoff:
                    self.long_term.delete(meta.chromadb_id)
                    db.delete(meta)
                    stats["deleted"] += 1
                    logger.info("memory_consolidated_deleted", chromadb_id=meta.chromadb_id)
                else:
                    meta.importance_score = round(new_importance, 4)
                    stats["decayed"] += 1

            db.commit()

        logger.info("consolidation_complete", user_id=user_id, **stats)
        return stats
