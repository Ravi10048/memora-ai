import { Brain, Search, Wrench, CheckCircle, AlertCircle, Database } from "lucide-react";
import { type AgentStep } from "../api/client";

interface ThinkingPanelProps {
  steps: AgentStep[];
}

const stepIcons: Record<string, typeof Brain> = {
  thinking: Brain,
  memory_read: Search,
  tool_call: Wrench,
  tool_result: Wrench,
  self_check: CheckCircle,
  memory_write: Database,
  error: AlertCircle,
};

const stepColors: Record<string, string> = {
  thinking: "text-purple-400",
  memory_read: "text-blue-400",
  tool_call: "text-amber-400",
  tool_result: "text-emerald-400",
  self_check: "text-cyan-400",
  memory_write: "text-indigo-400",
  error: "text-red-400",
};

const stepLabels: Record<string, string> = {
  thinking: "Thinking",
  memory_read: "Memory Search",
  tool_call: "Using Tool",
  tool_result: "Tool Result",
  self_check: "Self-Check",
  memory_write: "Saving Memory",
  error: "Error",
};

export default function ThinkingPanel({ steps }: ThinkingPanelProps) {
  const visibleSteps = steps.filter((s) =>
    ["thinking", "memory_read", "tool_call", "tool_result", "self_check", "memory_write", "error"].includes(s.type)
  );

  if (visibleSteps.length === 0) return null;

  return (
    <div className="bg-slate-900/80 border border-slate-700 rounded-xl p-4 space-y-3">
      <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
        Agent Thinking
      </h3>
      <div className="space-y-2 max-h-96 overflow-y-auto">
        {visibleSteps.map((step, i) => {
          const Icon = stepIcons[step.type] || Brain;
          const color = stepColors[step.type] || "text-slate-400";
          const label = stepLabels[step.type] || step.type;

          return (
            <div key={i} className="flex items-start gap-2 text-xs">
              <Icon className={`w-4 h-4 mt-0.5 flex-shrink-0 ${color}`} />
              <div>
                <span className={`font-medium ${color}`}>{label}</span>
                {step.tool && (
                  <span className="ml-1 px-1.5 py-0.5 bg-slate-800 rounded text-slate-400">
                    {step.tool}
                  </span>
                )}
                {step.store && (
                  <span className="ml-1 px-1.5 py-0.5 bg-slate-800 rounded text-slate-400">
                    {step.store}
                  </span>
                )}
                <p className="text-slate-400 mt-0.5">{step.content}</p>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
