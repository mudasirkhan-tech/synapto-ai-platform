import { API_URL, ApiError, authHeaders, errorFrom } from "./api";
import type { Source } from "./api";

export interface Usage { prompt_tokens: number | null; completion_tokens: number | null }
export interface DoneEvent {
  message_id: number | null; finish: "complete" | "stopped" | "error"; provider: string | null; model: string | null;
  label: string | null; latency_ms: number | null; first_token_ms: number | null; usage: Usage | null;
}

/** SSE events: meta, sources, status, fallback, tool_start, tool_result, token, error, done, title (see apps/api/app/routers/chat.py). */
export interface StreamHandlers {
  onMeta?: (m: { conversation_id: string; user_message_id: number }) => void;
  onSources?: (sources: Source[]) => void;
  onStatus?: (s: { phase: string; message: string; provider?: string; model?: string; label?: string }) => void;
  onFallback?: (f: { from: string; to: string; reason: string; slow: boolean; message: string }) => void;
  onToolStart?: (t: { n: number; tool: string; args: Record<string, unknown>; message: string }) => void;
  onToolResult?: (t: { n: number; tool: string; ok: boolean; preview: string }) => void;
  onToken?: (text: string, seq: number) => void;
  onError?: (message: string) => void;
  onDone?: (d: DoneEvent) => void;
  onTitle?: (t: { conversation_id: string; title: string }) => void;
}

async function streamSSE(path: string, body: unknown, h: StreamHandlers, signal: AbortSignal): Promise<void> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}/api/v1${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeaders() },
      body: JSON.stringify(body),
      signal,
    });
  } catch (e) {
    if (e instanceof DOMException && e.name === "AbortError") throw e;
    throw new ApiError(0, "Cannot reach the SYNAPTO API. Is it running?");
  }
  if (!res.ok || !res.body) throw await errorFrom(res);

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  const dispatch = (block: string) => {
    let event = "message";
    const data: string[] = [];
    for (const line of block.split("\n")) {
      if (line.startsWith("event:")) event = line.slice(6).trim();
      else if (line.startsWith("data:")) data.push(line.slice(5).trim());
    }
    if (!data.length) return;
    const payload = JSON.parse(data.join("\n"));
    if (event === "meta") h.onMeta?.(payload);
    else if (event === "token") h.onToken?.(payload.text, payload.seq);
    else if (event === "error") h.onError?.(payload.message);
    else if (event === "done") h.onDone?.(payload);
    else if (event === "title") h.onTitle?.(payload);
    else if (event === "sources") h.onSources?.(payload.sources);
    else if (event === "status") h.onStatus?.(payload);
    else if (event === "fallback") h.onFallback?.(payload);
    else if (event === "tool_start") h.onToolStart?.(payload);
    else if (event === "tool_result") h.onToolResult?.(payload);
  };

  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let idx: number;
    while ((idx = buffer.indexOf("\n\n")) !== -1) {
      dispatch(buffer.slice(0, idx));
      buffer = buffer.slice(idx + 2);
    }
  }
}

export const streamChat = (
  body: { conversation_id: string | null; message: string; document_ids: string[]; model?: string; use_knowledge: boolean; web_search: boolean; tools: boolean; fallback: boolean },
  h: StreamHandlers,
  signal: AbortSignal,
) => streamSSE("/chat/stream", body, h, signal);

export const streamRegenerate = (
  body: { conversation_id: string; model?: string; use_knowledge: boolean; web_search: boolean; tools: boolean; fallback: boolean },
  h: StreamHandlers,
  signal: AbortSignal,
) => streamSSE("/chat/regenerate", body, h, signal);
