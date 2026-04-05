from __future__ import annotations

import math
import uuid
from datetime import datetime, timezone
from dataclasses import dataclass, field

import chromadb
from chromadb.config import Settings as ChromaSettings

from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class MemoryResult:
    """A single result from long-term memory search."""
    text: str
    chromadb_id: str
    similarity: float
    recency_score: float
    final_score: float
    created_at: str  # ISO format
    metadata: dict = field(default_factory=dict)


class LongTermMemory:
    """ChromaDB-backed vector store for long-term memory.

    Implements recency-weighted retrieval:
        final_score = (similarity_weight × cosine_similarity) + (recency_weight × recency_score)
        recency_score = exp(-decay_rate × hours_since_creation)
    """

    COLLECTION_NAME = "long_term_memories"

    def __init__(self):
        self.client = chromadb.Client(ChromaSettings(
            persist_directory=settings.chroma_persist_dir,
            anonymized_telemetry=False,
        ))
        self.collection = self.client.get_or_create_collection(
            name=self.COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
        self.recency_weight = settings.long_term_recency_weight
        self.similarity_weight = 1.0 - self.recency_weight
        self.min_relevance = settings.long_term_min_relevance
        self.decay_rate = 0.01  # Per hour

    def store(
        self,
        text: str,
        user_id: str,
        conversation_id: int | None = None,
        importance: float = 0.5,
    ) -> str:
        """Store a memory in the vector store. Returns chromadb_id."""
        memory_id = f"mem_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).isoformat()

        self.collection.add(
            documents=[text],
            ids=[memory_id],
            metadatas=[{
                "user_id": user_id,
                "conversation_id": str(conversation_id) if conversation_id else "",
                "created_at": now,
                "importance": importance,
            }],
        )

        logger.info("memory_stored", chromadb_id=memory_id, user_id=user_id, text_preview=text[:80])
        return memory_id

    def search(
        self,
        query: str,
        user_id: str,
        n_results: int = 5,
    ) -> list[MemoryResult]:
        """Search memories with recency weighting.

        Steps:
            1. Vector similarity search in ChromaDB
            2. Calculate recency score for each result
            3. Combine: final = (sim_weight × similarity) + (rec_weight × recency)
            4. Filter by minimum relevance threshold
            5. Sort by final score
        """
        # Get more results than needed, then filter/re-rank
        raw_results = self.collection.query(
            query_texts=[query],
            n_results=min(n_results * 3, 20),
            where={"user_id": user_id},
        )

        if not raw_results or not raw_results["ids"] or not raw_results["ids"][0]:
            return []

        now = datetime.now(timezone.utc)
        results: list[MemoryResult] = []

        for i, doc_id in enumerate(raw_results["ids"][0]):
            document = raw_results["documents"][0][i]
            metadata = raw_results["metadatas"][0][i]
            # ChromaDB returns distances (0 = identical, 2 = opposite for cosine)
            # Convert to similarity: similarity = 1 - (distance / 2)
            distance = raw_results["distances"][0][i] if raw_results.get("distances") else 0
            similarity = 1.0 - (distance / 2.0)

            # Calculate recency score
            created_str = metadata.get("created_at", "")
            recency = self._recency_score(created_str, now)

            # Combined score
            final = (self.similarity_weight * similarity) + (self.recency_weight * recency)

            # Filter by minimum relevance (Gap #7)
            if final < self.min_relevance:
                continue

            results.append(MemoryResult(
                text=document,
                chromadb_id=doc_id,
                similarity=round(similarity, 3),
                recency_score=round(recency, 3),
                final_score=round(final, 3),
                created_at=created_str,
                metadata=metadata,
            ))

        # Sort by final score descending
        results.sort(key=lambda r: r.final_score, reverse=True)
        return results[:n_results]

    def delete(self, chromadb_id: str) -> None:
        """Delete a specific memory."""
        try:
            self.collection.delete(ids=[chromadb_id])
            logger.info("memory_deleted", chromadb_id=chromadb_id)
        except Exception as e:
            logger.warning("memory_delete_failed", chromadb_id=chromadb_id, error=str(e))

    def get_all(self, user_id: str, limit: int = 100) -> list[dict]:
        """Get all memories for a user (for memory bank page)."""
        results = self.collection.get(
            where={"user_id": user_id},
            limit=limit,
        )
        if not results or not results["ids"]:
            return []

        memories = []
        for i, doc_id in enumerate(results["ids"]):
            memories.append({
                "id": doc_id,
                "text": results["documents"][i],
                "metadata": results["metadatas"][i],
            })
        return memories

    def count(self, user_id: str) -> int:
        """Count memories for a user."""
        try:
            results = self.collection.get(where={"user_id": user_id})
            return len(results["ids"]) if results["ids"] else 0
        except Exception:
            return 0

    def _recency_score(self, created_at_str: str, now: datetime) -> float:
        """Calculate recency score: recent → close to 1.0, old → close to 0.0."""
        if not created_at_str:
            return 0.5
        try:
            created_at = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
            hours_ago = (now - created_at).total_seconds() / 3600
            return math.exp(-self.decay_rate * hours_ago)
        except Exception:
            return 0.5
