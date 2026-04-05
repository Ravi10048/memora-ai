import { Trash2, Clock, Hash } from "lucide-react";

interface MemoryCardProps {
  type: "entity" | "long-term";
  title: string;
  content: string;
  metadata?: Record<string, string>;
  confidence?: number;
  accessCount?: number;
  createdAt: string;
  onDelete: () => void;
}

export default function MemoryCard({
  type,
  title,
  content,
  metadata,
  confidence,
  accessCount,
  createdAt,
  onDelete,
}: MemoryCardProps) {
  return (
    <div
      className={`rounded-xl border p-4 transition-all hover:scale-[1.01] ${
        type === "entity"
          ? "border-purple-500/30 bg-purple-500/5"
          : "border-blue-500/30 bg-blue-500/5"
      }`}
    >
      <div className="flex items-start justify-between mb-2">
        <div>
          <span
            className={`text-xs font-medium px-2 py-0.5 rounded-full ${
              type === "entity"
                ? "bg-purple-500/20 text-purple-400"
                : "bg-blue-500/20 text-blue-400"
            }`}
          >
            {type === "entity" ? "Entity" : "Long-term"}
          </span>
          <h3 className="text-sm font-medium text-slate-200 mt-2">{title}</h3>
        </div>
        <button
          onClick={onDelete}
          className="p-1.5 rounded-lg text-slate-500 hover:text-red-400 hover:bg-red-500/10 transition-colors"
        >
          <Trash2 className="w-4 h-4" />
        </button>
      </div>

      <p className="text-xs text-slate-400 mb-3">{content}</p>

      {metadata && Object.keys(metadata).length > 0 && (
        <div className="flex flex-wrap gap-1 mb-2">
          {Object.entries(metadata).map(([k, v]) => (
            <span key={k} className="text-xs px-2 py-0.5 bg-slate-800 rounded text-slate-400">
              {k}: {v}
            </span>
          ))}
        </div>
      )}

      <div className="flex items-center gap-4 text-xs text-slate-500">
        {confidence !== undefined && (
          <span>Confidence: {Math.round(confidence * 100)}%</span>
        )}
        {accessCount !== undefined && (
          <span className="flex items-center gap-1">
            <Hash className="w-3 h-3" /> {accessCount} accesses
          </span>
        )}
        <span className="flex items-center gap-1">
          <Clock className="w-3 h-3" /> {new Date(createdAt).toLocaleDateString()}
        </span>
      </div>
    </div>
  );
}
