"use client";
import { BookOpen, Code2, FileText, Globe, ImageIcon, Loader2, Mic, Paperclip, Send, Square, Wrench, X } from "lucide-react";
import type { SpeechState } from "@/lib/useSpeechRecognition";
import { scriptClass } from "@/lib/text";
import AuthImage from "./AuthImage";

export interface ChatAttachment {
  id: string;
  filename: string;
  kind: "document" | "image";
  status: "processing" | "ready" | "failed";
  error?: string | null;
}

export type MicState = SpeechState | "transcribing";

interface Props {
  value: string;
  onChange: (v: string) => void;
  onSend: () => void;
  onStop: () => void;
  onPickDocs: () => void;
  onPickImages: () => void;
  attachments: ChatAttachment[];
  onRemoveAttachment: (id: string) => void;
  uploading: boolean;
  streaming: boolean;
  modelSelector: React.ReactNode;
  useKnowledge: boolean;
  onToggleKnowledge: () => void;
  webSearch: boolean;
  onToggleWeb: () => void;
  webAvailable: boolean | null;
  agentTools: boolean;
  onToggleTools: () => void;
  micState: MicState;
  micInterim: string;
  micMessage: string | null;
  onMic: () => void;
  onOpenCode: () => void;
}

const btn = "flex h-8 w-8 items-center justify-center rounded-lg border bg-white/[0.04] hover:bg-white/[0.08] disabled:opacity-50";
const idle = "border-line";
const on = "border-[#8b7bff] bg-brand/25 text-white";

export default function Composer(p: Props) {
  const micBusy = p.micState === "starting" || p.micState === "processing" || p.micState === "transcribing";
  const blocked = p.uploading || micBusy || p.attachments.some((a) => a.status !== "ready");
  const showStatus = p.attachments.length > 0 || p.uploading || p.micState !== "idle" || !!p.micMessage;

  return (
    <div className="rounded-2xl border border-line bg-card/95 p-3 shadow-[0_0_0_1px_rgba(124,92,255,.08)]">
      {showStatus && (
        <div className="mb-2 flex flex-wrap items-center gap-1.5" aria-live="polite">
          {p.attachments.map((a) => (
            <span key={a.id} title={a.error ?? undefined}
              className={`flex items-center gap-1.5 rounded-full border py-0.5 pl-1.5 pr-1 text-xs ${a.status === "failed" ? "border-red-500/50 bg-red-500/10" : "border-line bg-white/[0.05]"}`}>
              {a.kind === "image" ? <AuthImage id={a.id} alt="" className="h-5 w-5 rounded object-cover" /> : <FileText size={13} className="text-brand-soft" />}
              <span className="max-w-[160px] truncate">{a.filename}</span>
              {a.status === "processing" && <span className="flex items-center gap-1 text-[11px] text-white/55"><Loader2 size={11} className="animate-spin" />Indexing…</span>}
              {a.status === "failed" && <span className="text-[11px] text-red-300">failed</span>}
              <button onClick={() => p.onRemoveAttachment(a.id)} aria-label={`Remove ${a.filename}`} className="rounded-full p-0.5 hover:bg-white/10"><X size={12} /></button>
            </span>
          ))}
          {p.uploading && <span className="flex items-center gap-1.5 px-2 text-xs text-white/60"><Loader2 size={12} className="animate-spin" />Uploading…</span>}
          {p.micState === "starting" && <span className="flex items-center gap-1.5 px-2 text-xs text-white/60"><Loader2 size={12} className="animate-spin" />Starting microphone…</span>}
          {p.micState === "listening" && (
            <span dir="auto" className="flex max-w-full items-center gap-1.5 px-2 text-xs text-red-300">
              <span className="h-2 w-2 shrink-0 animate-pulse rounded-full bg-red-500" />Listening{p.micInterim ? `: ${p.micInterim}` : "… speak now"}
            </span>
          )}
          {(p.micState === "processing" || p.micState === "transcribing") && <span className="flex items-center gap-1.5 px-2 text-xs text-white/60"><Loader2 size={12} className="animate-spin" />Processing speech…</span>}
          {p.micMessage && <span role="alert" className="px-2 text-xs text-amber-300">{p.micMessage}</span>}
        </div>
      )}
      <textarea
        value={p.value}
        onChange={(e) => p.onChange(e.target.value)}
        onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); p.onSend(); } }}
        dir="auto"
        placeholder="Ask me anything..."
        aria-label="Message"
        rows={2}
        maxLength={8000}
        className={`w-full resize-none bg-transparent text-[14px] leading-snug text-white placeholder:text-white/60 focus:outline-none ${scriptClass(p.value)}`}
      />
      <div className="mt-2 flex items-center gap-2">
        <div className="flex flex-1 flex-wrap items-center gap-2">
          <button onClick={p.onPickDocs} className="flex h-8 items-center gap-1.5 rounded-lg border border-line bg-white/[0.04] px-2.5 text-[13px] hover:bg-white/[0.08]">
            <Paperclip size={15} />Attach File
          </button>
          <button onClick={p.onPickImages} aria-label="Attach image" title="Attach image (needs a vision-capable model)" className={`${btn} ${idle}`}><ImageIcon size={15} /></button>
          <button onClick={p.onMic} disabled={micBusy} aria-pressed={p.micState === "listening"}
            aria-label={p.micState === "listening" ? "Stop dictation" : "Dictate with microphone"} title="Voice input"
            className={`${btn} ${p.micState === "listening" ? "border-red-500 bg-red-500/20" : p.micState === "denied" ? "border-amber-500/60" : idle}`}><Mic size={15} /></button>
          <button onClick={p.onToggleKnowledge} aria-pressed={p.useKnowledge} aria-label="Search my documents" title="Search my document library"
            className={`${btn} ${p.useKnowledge ? on : idle}`}><BookOpen size={15} /></button>
          <button onClick={p.onToggleWeb} aria-pressed={p.webSearch} aria-label="Search the web"
            title={p.webAvailable === false ? "Web search isn't configured (see Web Search)" : "Add web search results"}
            className={`${btn} ${p.webSearch ? on : idle} ${p.webAvailable === false ? "opacity-60" : ""}`}><Globe size={15} /></button>
          <button onClick={p.onToggleTools} aria-pressed={p.agentTools} aria-label="Agent tools"
            title="Let the assistant use read-only tools (calculator, your documents, web) and show each step live"
            className={`${btn} ${p.agentTools ? on : idle}`}><Wrench size={15} /></button>
          <button onClick={p.onOpenCode} aria-label="Open code assistant" title="Code assistant" className={`${btn} ${idle}`}><Code2 size={15} /></button>
          {p.modelSelector}
        </div>
        {p.streaming ? (
          <button onClick={p.onStop} aria-label="Stop generating" className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-[#8b7bff] bg-white/[0.06]">
            <Square size={15} className="fill-white" />
          </button>
        ) : (
          <button onClick={p.onSend} disabled={!p.value.trim() || blocked} aria-label="Send"
            className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-[#4f6bff] to-[#6b4cf0] shadow-glow disabled:opacity-50 disabled:shadow-none">
            <Send size={17} />
          </button>
        )}
      </div>
    </div>
  );
}
