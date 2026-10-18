export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const TOKEN_KEY = "synapto.token";

export const tokenStore = {
  get: () => (typeof window === "undefined" ? null : window.localStorage.getItem(TOKEN_KEY)),
  set: (t: string) => window.localStorage.setItem(TOKEN_KEY, t),
  clear: () => window.localStorage.removeItem(TOKEN_KEY),
};

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

export async function errorFrom(res: Response): Promise<ApiError> {
  let message = `Request failed (${res.status})`;
  try {
    const body = await res.json();
    if (body?.error?.message) message = body.error.message;
  } catch { /* non-JSON error body */ }
  return new ApiError(res.status, message);
}

export function authHeaders(): Record<string, string> {
  const t = tokenStore.get();
  return t ? { Authorization: `Bearer ${t}` } : {};
}

async function raw(path: string, init: RequestInit & { json?: unknown } = {}): Promise<Response> {
  const headers: Record<string, string> = { ...authHeaders() };
  if (init.json !== undefined) headers["Content-Type"] = "application/json";
  let res: Response;
  try {
    res = await fetch(`${API_URL}/api/v1${path}`, {
      ...init,
      headers: { ...headers, ...(init.headers as Record<string, string>) },
      body: init.json !== undefined ? JSON.stringify(init.json) : init.body,
      cache: "no-store",
    });
  } catch {
    throw new ApiError(0, "Cannot reach the SYNAPTO API. Is it running on " + API_URL + "?");
  }
  if (!res.ok) throw await errorFrom(res);
  return res;
}

async function request<T>(path: string, init: RequestInit & { json?: unknown } = {}): Promise<T> {
  const res = await raw(path, init);
  return res.status === 204 ? (undefined as T) : res.json();
}

/* ---------- types ---------- */
export interface User { id: string; display_name: string; email: string | null; is_guest: boolean }
export interface TokenOut { access_token: string; user: User }
export interface Conversation { id: string; title: string; updated_at: string }
export interface AttachmentRef { id: string; filename: string; kind: "document" | "image" }
export interface Source { n: number; title: string; kind: "document" | "web"; document_id: string | null; page: number | null; url: string | null; snippet: string }
export interface StoredMessage { id: number; role: "user" | "assistant"; content: string; attachments: AttachmentRef[]; model: string | null; provider: string | null; finish: string | null; sources: Source[] }
export interface DocumentInfo {
  id: string; filename: string; kind: "document" | "image"; scope: string; status: "processing" | "ready" | "failed";
  error: string | null; chunk_count: number; char_count: number; embedded: boolean; size_bytes: number; created_at: string;
}
export interface ModelInfo { name: string; size_bytes: number | null; tags: string[] }
export interface CatalogModel { ref: string; label: string; model_id: string; state: string; detail: string; tags: string[]; vision: boolean | null }
export interface CatalogGroup { id: string; label: string; cloud: boolean; status: string; detail: string; models: CatalogModel[] }
export interface AutoInfo { ref: string | null; label: string; order: string[]; note: string }
export interface ModelsOut { default: string; reachable: boolean; models: ModelInfo[]; groups: CatalogGroup[]; auto: AutoInfo | null }
export interface ProviderInfo { id: string; label: string; env_var: string; configured: boolean; source: "user" | "server" | null; masked: string | null }
export interface WebResult { title: string; url: string; snippet: string }
export interface Feature { available: boolean; engine: string; setup: string }
export interface Capabilities {
  embeddings: { model: string; installed: boolean | null; setup: string };
  voice: Feature; web_search: Feature; image_generation: Feature;
}

export interface SystemStatus {
  api: { status: string; version: string; env: string };
  mode: string;
  runtime: {
    provider: string; base_url: string; reachable: boolean; version: string | null; latency_ms: number | null;
    models: { name: string; size_bytes: number | null }[]; required_model: string; model_ready: boolean; error: string | null;
  };
}

/* ---------- endpoints ---------- */
export const fetchStatus = (signal?: AbortSignal) => request<SystemStatus>("/status", { signal });

export const register = (email: string, password: string, display_name?: string) =>
  request<TokenOut>("/auth/register", { method: "POST", json: { email, password, display_name } });
export const login = (email: string, password: string) => request<TokenOut>("/auth/login", { method: "POST", json: { email, password } });
export const loginGuest = () => request<TokenOut>("/auth/guest", { method: "POST" });
export const getMe = () => request<User>("/auth/me");

export const listConversations = () => request<Conversation[]>("/conversations?limit=50");
export const getMessages = (id: string) => request<StoredMessage[]>(`/conversations/${id}/messages`);
export const deleteConversation = (id: string) => request<void>(`/conversations/${id}`, { method: "DELETE" });
export const deleteAllConversations = () => request<void>("/conversations", { method: "DELETE" });
export const exportChats = () => request<unknown>("/conversations/export");

export const listModels = () => request<ModelsOut>("/models");
export const getCapabilities = () => request<Capabilities>("/capabilities");

export function uploadDocument(file: File, scope: "library" | "chat") {
  const form = new FormData();
  form.append("file", file);
  form.append("scope", scope);
  return request<DocumentInfo>("/documents", { method: "POST", body: form });
}
export const listDocuments = (scope: "library") => request<DocumentInfo[]>(`/documents?scope=${scope}`);
export const getDocument = (id: string) => request<DocumentInfo>(`/documents/${id}`);
export const deleteDocument = (id: string) => request<void>(`/documents/${id}`, { method: "DELETE" });
export const reindexDocument = (id: string) => request<DocumentInfo>(`/documents/${id}/reindex`, { method: "POST" });
export async function documentBlob(id: string): Promise<Blob> {
  return (await raw(`/documents/${id}/file`)).blob();
}

export function transcribe(audio: Blob, language?: string) {
  const form = new FormData();
  form.append("audio", audio, "recording.webm");
  if (language) form.append("language", language);
  return request<{ text: string; language: string | null }>("/voice/transcribe", { method: "POST", body: form });
}

export const webSearch = (query: string) => request<WebResult[]>("/search", { method: "POST", json: { query } });

export const generateImage = (b: { prompt: string; negative_prompt?: string; width: number; height: number; steps: number }) =>
  request<DocumentInfo>("/images/generate", { method: "POST", json: b });
export const listImages = () => request<DocumentInfo[]>("/images");

export const calculate = (expression: string) => request<{ result: number }>("/tools/calculate", { method: "POST", json: { expression } });
export const unitCatalog = () => request<Record<string, string[]>>("/tools/units");
export const convertUnits = (value: number, from_unit: string, to_unit: string) =>
  request<{ result: number }>("/tools/convert", { method: "POST", json: { value, from_unit, to_unit } });

/* ---------- agent ---------- */
export interface AgentStep {
  id: number; idx: number; kind: "tool_call" | "tool_result" | "note" | "info" | "error" | "final";
  tool: string | null; args: Record<string, unknown> | null; content: string; status: string; created_at: string;
}
export type AgentStatus = "queued" | "running" | "waiting_approval" | "completed" | "failed" | "cancelled";
export interface AgentTask {
  id: string; goal: string; status: AgentStatus; model: string; use_knowledge: boolean; web_search: boolean;
  final_answer: string | null; error: string | null; created_at: string; updated_at: string; steps: AgentStep[];
}
export interface AgentToolInfo { name: string; description: string; requires_approval: boolean; available: boolean; note: string }

export const listAgentTools = () => request<AgentToolInfo[]>("/agent/tools");
export const listAgentTasks = () => request<AgentTask[]>("/agent/tasks");
export const getAgentTask = (id: string) => request<AgentTask>(`/agent/tasks/${id}`);
export const createAgentTask = (b: { goal: string; model?: string; use_knowledge: boolean; web_search: boolean }) =>
  request<AgentTask>("/agent/tasks", { method: "POST", json: b });
export const cancelAgentTask = (id: string) => request<AgentTask>(`/agent/tasks/${id}/cancel`, { method: "POST" });
export const decideAgentTask = (id: string, approve: boolean) =>
  request<AgentTask>(`/agent/tasks/${id}/decision`, { method: "POST", json: { approve } });
export const deleteAgentTask = (id: string) => request<void>(`/agent/tasks/${id}`, { method: "DELETE" });

/* ---------- providers / API keys (write-only: the server never returns a key) ---------- */
export const listProviders = () => request<ProviderInfo[]>("/providers");
export const saveProviderKey = (id: string, api_key: string) => request<ProviderInfo>(`/providers/${id}/key`, { method: "PUT", json: { api_key } });
export const deleteProviderKey = (id: string) => request<ProviderInfo>(`/providers/${id}/key`, { method: "DELETE" });
export const testProvider = (id: string, api_key?: string) =>
  request<{ ok: boolean; message: string }>(`/providers/${id}/test`, { method: "POST", json: api_key ? { api_key } : {} });
