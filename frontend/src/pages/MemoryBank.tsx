import { useEffect, useState } from "react";
import { Brain, Database, Search } from "lucide-react";
import MemoryCard from "../components/MemoryCard";
import {
  fetchEntities,
  fetchLongTermMemories,
  deleteEntity,
  deleteLongTermMemory,
  type Entity,
  type LongTermMemory,
} from "../api/client";

type Tab = "entity" | "long-term";

export default function MemoryBank() {
  const [tab, setTab] = useState<Tab>("entity");
  const [entities, setEntities] = useState<Entity[]>([]);
  const [memories, setMemories] = useState<LongTermMemory[]>([]);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    const [e, m] = await Promise.all([fetchEntities(), fetchLongTermMemories()]);
    setEntities(e);
    setMemories(m);
    setLoading(false);
  };

  useEffect(() => { load(); }, []);

  const handleDeleteEntity = async (id: number) => {
    await deleteEntity(id);
    setEntities((prev) => prev.filter((e) => e.id !== id));
  };

  const handleDeleteMemory = async (id: number) => {
    await deleteLongTermMemory(id);
    setMemories((prev) => prev.filter((m) => m.id !== id));
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-purple-500" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-100">Memory Bank</h1>
        <p className="text-slate-400 mt-1">
          {entities.length} entities, {memories.length} long-term memories
        </p>
      </div>

      {/* Tabs */}
      <div className="flex gap-2">
        <button
          onClick={() => setTab("entity")}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
            tab === "entity"
              ? "bg-purple-600 text-white"
              : "bg-slate-800 text-slate-400 hover:bg-slate-700"
          }`}
        >
          <Brain className="w-4 h-4" /> Entities ({entities.length})
        </button>
        <button
          onClick={() => setTab("long-term")}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
            tab === "long-term"
              ? "bg-blue-600 text-white"
              : "bg-slate-800 text-slate-400 hover:bg-slate-700"
          }`}
        >
          <Database className="w-4 h-4" /> Long-term ({memories.length})
        </button>
      </div>

      {/* Content */}
      {tab === "entity" && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {entities.length === 0 ? (
            <p className="text-slate-500 col-span-2 text-center py-12">
              No entities stored yet. Start chatting to build memory.
            </p>
          ) : (
            entities.map((e) => (
              <MemoryCard
                key={e.id}
                type="entity"
                title={e.name}
                content={`Type: ${e.type}`}
                metadata={e.attributes}
                confidence={e.confidence}
                accessCount={e.access_count}
                createdAt={e.created_at}
                onDelete={() => handleDeleteEntity(e.id)}
              />
            ))
          )}
        </div>
      )}

      {tab === "long-term" && (
        <div className="space-y-3">
          {memories.length === 0 ? (
            <p className="text-slate-500 text-center py-12">
              No long-term memories yet. They're created automatically from conversations.
            </p>
          ) : (
            memories.map((m) => (
              <MemoryCard
                key={m.id}
                type="long-term"
                title={m.text.slice(0, 80) + (m.text.length > 80 ? "..." : "")}
                content={m.text}
                accessCount={m.access_count}
                createdAt={m.created_at}
                onDelete={() => handleDeleteMemory(m.id)}
              />
            ))
          )}
        </div>
      )}
    </div>
  );
}
