"use client";
import { AlertTriangle, Check, CheckCircle2, Copy, FileText, Globe, Loader2, Pause, Play, RefreshCw, Square, Volume2, Wrench, XCircle } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import type { AttachmentRef, Source } from "@/lib/api";
import { copyText } from "@/lib/clipboard";
import { detectDir, scriptClass } from "@/lib/text";
import type { SpeechSynthState } from "@/lib/useSpeechSynthesis";
import AuthImage from "./AuthImage";
import Logo from "./Logo";
import MarkdownView from "./MarkdownView";

export type ActivityItem =
  | { kind: "tool"; n: number; tool: string; message: string; args?: Record<string, unknown>; state: "running" | "ok" | "error"; preview?: string }
  | { kind: "fallback"; message: string; slow: boolean };

export interface ChatMessage {
  id?: number;
  role: "user" | "assistant";
  content: string;
  attachments?: AttachmentRef[];
  sources?: Source[];
  model?: string | null;
  provider?: string | null;
  finish?: string | null;
  latencyMs?: number | null;
  streaming?: boolean;
  status?: string | null;
  activity?: ActivityItem[];
}

const PROVIDER = { deepseek: "DeepSeek", gemini: "Gemini", ollama: "Local" } as Record<string, string>;

function CopyReply({ text }: { text: string }) {
  const [done, setDone] = useState(false);
  return (
    <button aria-label="Copy response" onClick={async () => { if (await copyText(text)) { setDone(true); setTimeout(() => setDone(false), 1500); } }}
      className="flex items-center gap-1.5 rounded-md px-2 py-1 text-xs text-white/55 hover:bg-white/10 hover:text-white">
      {done ? <Check size={13} className="text-emerald-400" /> : <Copy size={13} />}{done ? "Copied" : "Copy"}
    </button>
  );
}

function SourceList({ sources }: { sources: Source[] }) {
  return (
    <details className="mt-2 rounded-lg border border-line bg-white/[0.03] px-3 py-1.5 text-xs text-white/70">
      <summary className="cursor-pointer select-none">Sources ({sources.length})</summary>
      <ul className="mt-1.5 space-y-1.5 pb-1">
        {sources.map((s) => (
          <li key={s.n} dir="auto" className="flex gap-2">
            <span className="shrink-0 text-brand-soft">[{s.n}]</span>
            <span className="min-w-0">
              <span className="flex items-center gap-1.5 text-white/85">
                {s.kind === "web" ? <Globe size={12} /> : <FileText size={12} />}
                {s.url ? <a href={s.url} target="_blank" rel="noopener noreferrer" className="truncate underline">{s.title}</a> : <span className="truncate">{s.title}</span>}
                {s.page ? <span className="text-white/45">p.{s.page}</span> : null}
              </span>
              {s.snippet && <span className="line-clamp-2 text-white/50">{s.snippet}</span>}
            </span>
          </li>
        ))}
      </ul>
    </details>
  );
}

/** Real activity only: every row comes from an event the server actually emitted. */
function Activity({ items }: { items: ActivityItem[] }) {
  return (
    <ul className="mb-2 space-y-1">
      {items.map((a, i) =>
        a.kind === "fallback" ? (
          <li key={i} className={`flex items-start gap-1.5 rounded-lg border px-2.5 py-1.5 text-xs ${a.slow ? "border-amber-500/40 bg-amber-500/10 text-amber-100" : "border-line bg-white/[0.03] text-white/70"}`}>
            <AlertTriangle size={13} className="mt-0.5 shrink-0" />{a.message}
          </li>
        ) : (
          <li key={i} className="rounded-lg border border-line bg-white/[0.03] px-2.5 py-1.5 text-xs">
            <div className="flex items-center gap-1.5 text-white/80">
              {a.state === "running" ? <Loader2 size={13} className="animate-spin" /> : a.state === "ok" ? <CheckCircle2 size={13} className="text-emerald-400" /> : <XCircle size={13} className="text-red-300" />}
              <Wrench size={12} className="text-brand-soft" /><b>{a.tool}</b>
              <span className="text-white/50">{a.state === "running" ? a.message : a.state === "ok" ? "done" : "failed"}</span>
            </div>
            {a.args && Object.keys(a.args).length > 0 && <div dir="auto" className="mt-0.5 truncate text-[11px] text-white/45">{Object.entries(a.args).map(([k, v]) => `${k}: ${v}`).join(", ")}</div>}
            {a.preview && <details className="mt-0.5"><summary className="cursor-pointer text-[11px] text-white/50">Result</summary><pre dir="auto" className="thin-scroll mt-1 max-h-32 overflow-auto whitespace-pre-wrap break-words text-[11px] text-white/65">{a.preview}</pre></details>}
          </li>
        ),
      )}
    </ul>
  );
}

export default function ChatMessages({ messages, busy, onRegenerate, onStop, speech, speechNote }: {
  messages: ChatMessage[]; busy: boolean; onRegenerate: () => void; onStop: () => void; speech: SpeechSynthState; speechNote: string | null;
}) {
  const box = useRef<HTMLDivElement>(null);
  const end = useRef<HTMLDivElement>(null);
  const stick = useRef(true);

  useEffect(() => { if (stick.current) end.current?.scrollIntoView({ block: "end" }); }, [messages]);
  const onScroll = () => {
    const el = box.current;
    if (el) stick.current = el.scrollHeight - el.scrollTop - el.clientHeight < 120;
  };
  const last = messages.length - 1;

  return (
    <div ref={box} onScroll={onScroll} className="thin-scroll min-h-0 flex-1 xl:overflow-y-auto" aria-live="polite">
      <div className="mx-auto w-full max-w-[820px] space-y-5 pb-3 pr-1">
        {messages.map((m, i) =>
          m.role === "user" ? (
            <div key={i} className="flex flex-col items-end gap-1.5">
              {!!m.attachments?.length && (
                <div className="flex flex-wrap justify-end gap-1.5">
                  {m.attachments.map((a) =>
                    a.kind === "image" ? (
                      <AuthImage key={a.id} id={a.id} alt={a.filename} className="h-20 w-20 rounded-lg border border-line object-cover" />
                    ) : (
                      <span key={a.id} className="flex items-center gap-1 rounded-full border border-line bg-white/[0.04] px-2.5 py-0.5 text-[11px] text-white/80"><FileText size={11} />{a.filename}</span>
                    ),
                  )}
                </div>
              )}
              <div dir={detectDir(m.content)} className={`max-w-[85%] whitespace-pre-wrap break-words rounded-2xl rounded-br-md bg-gradient-to-br from-[#4b34b8] to-[#6a4cf0] px-3.5 py-2 text-[14px] leading-relaxed ${scriptClass(m.content)}`}>
                {m.content}
              </div>
              {i === last && !busy && (
                <button onClick={onRegenerate} className="flex items-center gap-1.5 rounded-md px-2 py-1 text-xs text-white/60 hover:bg-white/10 hover:text-white"><RefreshCw size={13} />Retry</button>
              )}
            </div>
          ) : (
            <div key={i} className="flex gap-2.5">
              <div className="mt-0.5 shrink-0"><Logo size={26} /></div>
              <div className="min-w-0 flex-1">
                {!!m.activity?.length && <Activity items={m.activity} />}
                {m.streaming && m.status && (
                  <div className="mb-1 flex items-center gap-2 text-xs text-white/60" role="status">
                    <Loader2 size={13} className="animate-spin" />{m.status}
                    <button onClick={onStop} className="ml-1 rounded px-1.5 py-0.5 text-[11px] text-white/55 underline hover:text-white">Cancel</button>
                  </div>
                )}
                {m.content ? <MarkdownView content={m.content} /> : null}
                {m.streaming && !m.status && <span className="inline-block h-[1.1em] w-[0.5em] translate-y-[3px] animate-pulse bg-brand-soft" />}
                {!m.streaming && !!m.sources?.length && <SourceList sources={m.sources} />}
                {!m.streaming && m.finish && m.finish !== "complete" && (
                  <p className="mt-1 flex items-center gap-1.5 text-xs text-amber-300"><AlertTriangle size={13} />{m.finish === "stopped" ? "Stopped. This reply is incomplete." : "Operation failed. This reply is incomplete."}</p>
                )}
                {!m.streaming && m.content && (
                  <div className="mt-1.5 flex flex-wrap items-center gap-1 text-white/55">
                    <CopyReply text={m.content} />
                    {speech.supported && (speech.speakingId === String(i) ? (
                      <>
                        <button onClick={speech.paused ? speech.resume : speech.pause} aria-label={speech.paused ? "Resume speech" : "Pause speech"} className="flex items-center gap-1.5 rounded-md px-2 py-1 text-xs hover:bg-white/10 hover:text-white">
                          {speech.paused ? <Play size={13} /> : <Pause size={13} />}{speech.paused ? "Resume" : "Pause"}
                        </button>
                        <button onClick={speech.stop} aria-label="Stop speech" className="flex items-center gap-1.5 rounded-md px-2 py-1 text-xs hover:bg-white/10 hover:text-white"><Square size={12} />Stop</button>
                      </>
                    ) : (
                      <button onClick={() => speech.speak(String(i), m.content)} aria-label="Listen to this reply" className="flex items-center gap-1.5 rounded-md px-2 py-1 text-xs hover:bg-white/10 hover:text-white"><Volume2 size={13} />Listen</button>
                    ))}
                    {i === last && (
                      <button onClick={onRegenerate} disabled={busy} aria-label="Regenerate response" className="flex items-center gap-1.5 rounded-md px-2 py-1 text-xs hover:bg-white/10 hover:text-white disabled:opacity-40"><RefreshCw size={13} />Regenerate</button>
                    )}
                    {(m.provider || m.model) && (
                      <span className="ml-auto flex items-center gap-1.5 text-[11px] text-white/40">
                        {m.finish === "complete" || !m.finish ? <CheckCircle2 size={12} className="text-emerald-400/70" /> : null}
                        {m.provider ? PROVIDER[m.provider] ?? m.provider : ""}{m.model ? ` · ${m.model}` : ""}{m.latencyMs ? ` · ${(m.latencyMs / 1000).toFixed(1)}s` : ""}
                      </span>
                    )}
                  </div>
                )}
                {speech.speakingId === String(i) && speechNote && <p className="mt-1 text-[11px] text-amber-300">{speechNote}</p>}
              </div>
            </div>
          ),
        )}
        <div ref={end} />
      </div>
    </div>
  );
}
