import axios from "axios";

const api = axios.create({ baseURL: "/api" });

// ── Types ──

export interface Conversation {
  id: number;
  title: string;
  message_count: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface Message {
  id: number;
  role: "user" | "assistant" | "system" | "tool";
  content: string;
  created_at: string;
}

export interface ConversationDetail extends Conversation {
  messages: Message[];
}

export interface Entity {
  id: number;
  name: string;
  type: string;
  attributes: Record<string, string>;
  confidence: number;
  access_count: number;
  created_at: string;
  updated_at: string;
}

export interface LongTermMemory {
  id: number;
  chromadb_id: string;
  text: string;
  importance: number;
  access_count: number;
  last_accessed: string | null;
  created_at: string;
}

export interface AgentStep {
  type: "thinking" | "memory_read" | "tool_call" | "tool_result" | "self_check" | "token" | "memory_write" | "done" | "error";
  content: string;
  tool: string;
  store: string;
  confident: boolean;
  metadata: Record<string, unknown>;
}

export interface AppSettings {
  llm_provider: string;
  groq_model: string;
  ollama_model: string;
  short_term_max_messages: number;
  long_term_min_relevance: number;
  long_term_recency_weight: number;
  entity_confidence_threshold: number;
}

// ── API Functions ──

export const fetchConversations = async (): Promise<Conversation[]> => {
  const { data } = await api.get("/conversations");
  return data;
};

export const fetchConversation = async (id: number): Promise<ConversationDetail> => {
  const { data } = await api.get(`/conversations/${id}`);
  return data;
};

export const createConversation = async (): Promise<{ id: number; title: string }> => {
  const { data } = await api.post("/conversations");
  return data;
};

export const deleteConversation = async (id: number): Promise<void> => {
  await api.delete(`/conversations/${id}`);
};

export const fetchEntities = async (): Promise<Entity[]> => {
  const { data } = await api.get("/memory/entities");
  return data;
};

export const deleteEntity = async (id: number): Promise<void> => {
  await api.delete(`/memory/entities/${id}`);
};

export const fetchLongTermMemories = async (): Promise<LongTermMemory[]> => {
  const { data } = await api.get("/memory/long-term");
  return data;
};

export const deleteLongTermMemory = async (id: number): Promise<void> => {
  await api.delete(`/memory/long-term/${id}`);
};

export const searchMemory = async (query: string) => {
  const { data } = await api.post("/memory/search", { query });
  return data;
};

export const fetchSettings = async (): Promise<AppSettings> => {
  const { data } = await api.get("/settings");
  return data;
};

export const fetchHealth = async () => {
  const { data } = await api.get("/settings/health");
  return data;
};

export default api;
