"use client";
import { Check, Copy, Loader2, Mic, Send, Square, Upload } from "lucide-react";
import { useRef, useState } from "react";
import { transcribe } from "@/lib/api";
import type { Capabilities } from "@/lib/api";
import { copyText } from "@/lib/clipboard";
import { SPEECH_LANGS } from "@/lib/languages";
import { scriptClass } from "@/lib/text";
import { useRecorder } from "@/lib/useRecorder";
import { useSpeechRecognition } from "@/lib/useSpeechRecognition";
import ViewShell, { SetupNotice, card, ghost, input, primary } from "./ViewShell";

export default function VoiceView({ caps, lang, onLang, onBack, onError, onSendToChat }: {
  caps: Capabilities | null; lang: string; onLang: (v: string) => void; onBack: () => void; onError: (e: unknown) => void; onSendToChat: (text: string) => void;
}) {
  const [text, setText] = useState("");
  const [interim, setInterim] = useState("");
  const [copied, setCopied] = useState(false);
  const [busy, setBusy] = useState(false);
  const picker = useRef<HTMLInputElement>(null);
  const recorder = useRecorder();
  const speech = useSpeechRecognition({ lang, onFinal: (t) => setText((cur) => (cur ? `${cur} ${t}` : t)), onInterim: setInterim });
  const whisper = caps?.voice.available ?? false;
  const whisperLang = lang.split("-")[0];

  // Local Whisper is only used when the browser has no speech recognition (or for uploaded audio files).
  const runWhisper = async (audio: Blob) => {
    setBusy(true);
    try { const r = await transcribe(audio, whisperLang); setText((cur) => (cur ? `${cur}\n${r.text}` : r.text)); }
    catch (e) { onError(e); } finally { setBusy(false); }
  };

  const toggle = async () => {
    if (speech.supported) { speech.listening ? speech.stop() : speech.start(); return; }
    try {
      if (recorder.recording) { const blob = await recorder.stop(); if (blob?.size) await runWhisper(blob); }
      else if (whisper) await recorder.start();
    } catch { onError(new Error("Microphone access was denied or is unavailable.")); }
  };

  const listening = speech.supported ? speech.listening : recorder.recording;
  const canRecord = speech.supported ? speech.state === "idle" || speech.listening || speech.state === "error" || speech.state === "denied" : whisper;

  return (
    <ViewShell title="Voice" subtitle="Dictate with your browser's speech recognition; local Whisper is the fallback" icon={Mic} onBack={onBack}>
      {caps && !speech.supported && !whisper && <SetupNotice title="Speech recognition isn't available" text={`${caps.voice.setup} Or use a browser with built-in speech recognition (Chrome or Edge).`} />}
      <div className={`${card} space-y-3`}>
        <div className="flex flex-wrap items-center gap-2.5">
          <select value={lang} onChange={(e) => onLang(e.target.value)} disabled={listening} className={`${input} !w-auto`} aria-label="Spoken language">
            {SPEECH_LANGS.map(([code, name]) => <option key={code} value={code}>{name}</option>)}
          </select>
          <button onClick={toggle} disabled={!canRecord || busy || speech.state === "starting" || speech.state === "processing"} aria-pressed={listening}
            className={`${primary} flex items-center gap-2 ${listening ? "!bg-red-600" : ""}`}>
            {listening ? <Square size={14} className="fill-white" /> : <Mic size={14} />}{listening ? "Stop" : "Start dictating"}
          </button>
          <input ref={picker} type="file" accept="audio/*,video/webm" hidden onChange={(e) => { const f = e.target.files?.[0]; if (f) runWhisper(f); e.target.value = ""; }} />
          {whisper && <button onClick={() => picker.current?.click()} disabled={busy || listening} className={`${ghost} flex items-center gap-2`}><Upload size={14} />Transcribe audio file (Whisper)</button>}
          {(busy || speech.state === "starting" || speech.state === "processing") && <span className="flex items-center gap-1.5 text-xs text-white/60"><Loader2 size={13} className="animate-spin" />Processing…</span>}
        </div>
        <p className="text-[11px] text-white/45" role="status">
          {speech.supported ? "Using browser speech recognition. Depending on the browser, audio may be processed by its vendor's service." : "This browser has no speech recognition. Using local Whisper if installed."}
        </p>
        {speech.state === "listening" && <p dir="auto" className="text-xs text-red-300"><span className="mr-1.5 inline-block h-2 w-2 animate-pulse rounded-full bg-red-500" />Listening{interim ? `: ${interim}` : "… speak now"}</p>}
        {speech.message && <p role="alert" className="text-xs text-amber-300">{speech.message}</p>}
        <textarea dir="auto" value={text} onChange={(e) => setText(e.target.value)} rows={8} aria-label="Transcript" placeholder="Your transcript appears here. Edit it before sending."
          className={`${input} resize-none text-[14px] ${scriptClass(text)}`} />
        <div className="flex gap-2">
          <button disabled={!text.trim()} onClick={async () => { if (await copyText(text)) { setCopied(true); setTimeout(() => setCopied(false), 1500); } }} className={`${ghost} flex items-center gap-2`}>
            {copied ? <Check size={14} className="text-emerald-400" /> : <Copy size={14} />}Copy
          </button>
          <button disabled={!text.trim()} onClick={() => setText("")} className={ghost}>Clear</button>
          <button disabled={!text.trim()} onClick={() => onSendToChat(text.trim())} className={`${primary} ml-auto flex items-center gap-2`}><Send size={14} />Send to chat</button>
        </div>
      </div>
    </ViewShell>
  );
}
