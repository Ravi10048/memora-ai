import { useEffect, useState } from "react";
import { RefreshCw, CheckCircle, XCircle } from "lucide-react";
import { fetchSettings, fetchHealth, type AppSettings } from "../api/client";

export default function Settings() {
  const [settings, setSettings] = useState<AppSettings | null>(null);
  const [health, setHealth] = useState<{ status: string; provider?: string; model?: string; error?: string } | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([fetchSettings(), fetchHealth()]).then(([s, h]) => {
      setSettings(s);
      setHealth(h);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, []);

  const refreshHealth = async () => {
    const h = await fetchHealth();
    setHealth(h);
  };

  if (loading || !settings) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-purple-500" />
      </div>
    );
  }

  return (
    <div className="space-y-8 max-w-2xl">
      <div>
        <h1 className="text-2xl font-bold text-slate-100">Settings</h1>
        <p className="text-slate-400 mt-1">Agent configuration</p>
      </div>

      {/* Health */}
      <div className="bg-slate-800/50 rounded-xl border border-slate-700 p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-slate-100">LLM Provider Status</h2>
          <button onClick={refreshHealth} className="p-2 rounded-lg text-slate-400 hover:bg-slate-700">
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
        {health && (
          <div className="flex items-center gap-3">
            {health.status === "healthy" ? (
              <CheckCircle className="w-5 h-5 text-emerald-400" />
            ) : (
              <XCircle className="w-5 h-5 text-red-400" />
            )}
            <div>
              <span className={health.status === "healthy" ? "text-emerald-400" : "text-red-400"}>
                {health.status === "healthy" ? "Connected" : "Disconnected"}
              </span>
              {health.provider && (
                <p className="text-xs text-slate-500 mt-0.5">{health.provider} / {health.model}</p>
              )}
              {health.error && <p className="text-xs text-red-400 mt-0.5">{health.error}</p>}
            </div>
          </div>
        )}
      </div>

      {/* LLM Config */}
      <div className="bg-slate-800/50 rounded-xl border border-slate-700 p-6 space-y-3">
        <h2 className="text-lg font-semibold text-slate-100">LLM Configuration</h2>
        <div className="grid grid-cols-2 gap-4 text-sm">
          <div>
            <span className="text-slate-400">Provider</span>
            <p className="text-slate-200 font-medium">{settings.llm_provider}</p>
          </div>
          <div>
            <span className="text-slate-400">Model</span>
            <p className="text-slate-200 font-medium">{settings.groq_model}</p>
          </div>
        </div>
      </div>

      {/* Memory Config */}
      <div className="bg-slate-800/50 rounded-xl border border-slate-700 p-6 space-y-3">
        <h2 className="text-lg font-semibold text-slate-100">Memory Configuration</h2>
        <div className="grid grid-cols-2 gap-4 text-sm">
          <div>
            <span className="text-slate-400">Short-term window</span>
            <p className="text-slate-200 font-medium">{settings.short_term_max_messages} messages</p>
          </div>
          <div>
            <span className="text-slate-400">Min relevance threshold</span>
            <p className="text-slate-200 font-medium">{settings.long_term_min_relevance}</p>
          </div>
          <div>
            <span className="text-slate-400">Recency weight</span>
            <p className="text-slate-200 font-medium">{settings.long_term_recency_weight}</p>
          </div>
          <div>
            <span className="text-slate-400">Entity confidence threshold</span>
            <p className="text-slate-200 font-medium">{settings.entity_confidence_threshold}</p>
          </div>
        </div>
      </div>
    </div>
  );
}
