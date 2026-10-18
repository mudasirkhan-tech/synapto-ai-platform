"use client";
import { Check, Copy, Download, LogOut, Settings, Trash2, Volume2 } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { deleteAllConversations, exportChats, listProviders } from "@/lib/api";
import type { Capabilities, ProviderInfo } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { copyText } from "@/lib/clipboard";
import { SPEECH_LANGS } from "@/lib/languages";
import { getReplyScale, setReplyScale } from "@/lib/prefs";
import type { ModelsState } from "@/lib/useModels";
import { USABLE } from "@/lib/useModels";
import type { SpeechSynthState } from "@/lib/useSpeechSynthesis";
import ApiKeyCard from "./ApiKeyCard";
import ViewShell, { card, ghost, input } from "./ViewShell";

const RECOMMENDED = [
  { cmd: "ollama pull qwen2.5:7b", why: "Local multilingual chat model (used only when cloud models are unavailable or chosen)", match: "qwen2.5:7b" },
  { cmd: "ollama pull llama3.2-vision", why: "Local model that reads images", match: "llama3.2-vision" },
  { cmd: "ollama pull bge-m3", why: "Multilingual embeddings for document search (needed even with cloud chat models)", match: "bge-m3" },
];

function Cmd({ cmd }: { cmd: string }) {
  const [done, setDone] = useState(false);
  return (
    <button onClick={async () => { if (await copyText(cmd)) { setDone(true); setTimeout(() => setDone(false), 1500); } }} aria-label={`Copy ${cmd}`}
      className="flex items-center gap-1.5 rounded-md border border-line px-2 py-1 font-mono text-[11px] hover:bg-white/5">
      {done ? <Check size={12} className="text-emerald-400" /> : <Copy size={12} />}{cmd}
    </button>
  );
}

function Toggle({ on, onChange, label, hint }: { on: boolean; onChange: (v: boolean) => void; label: string; hint?: string }) {
  return (
    <label className="flex cursor-pointer items-start gap-3">
      <input type="checkbox" role="switch" checked={on} onChange={(e) => onChange(e.target.checked)} className="mt-1" />
      <span><span className="block text-[13px]">{label}</span>{hint && <span className="block text-[11px] text-white/50">{hint}</span>}</span>
    </label>
  );
}

export default function SettingsView({ models, caps, onBack, onError, onDataDeleted, fallback, onFallback, speechLang, onSpeechLang, voiceURI, onVoiceURI, tts }: {
  models: ModelsState; caps: Capabilities | null; onBack: () => void; onError: (e: unknown) => void; onDataDeleted: () => void;
  fallback: boolean; onFallback: (v: boolean) => void; speechLang: string; onSpeechLang: (v: string) => void;
  voiceURI: string | null; onVoiceURI: (v: string) => void; tts: SpeechSynthState;
}) {
  const { user, logout } = useAuth();
  const [scale, setScale] = useState(getReplyScale);
  const [providers, setProviders] = useState<ProviderInfo[] | null>(null);

  const loadProviders = useCallback(() => { listProviders().then(setProviders).catch(onError); }, [onError]);
  useEffect(() => { loadProviders(); }, [loadProviders]);
  const keysChanged = () => { loadProviders(); models.refresh(); };

  const installed = (match: string) => match === "bge-m3" ? caps?.embeddings.installed === true : models.flat.some((m) => m.model_id.startsWith(match));

  const doExport = async () => {
    try {
      const url = URL.createObjectURL(new Blob([JSON.stringify(await exportChats(), null, 2)], { type: "application/json" }));
      const a = document.createElement("a");
      a.href = url; a.download = "synapto-chats.json"; a.click();
      URL.revokeObjectURL(url);
    } catch (e) { onError(e); }
  };

  const wipe = async () => {
    if (!window.confirm("Delete ALL your chats and their attached images? This cannot be undone.")) return;
    try { await deleteAllConversations(); onDataDeleted(); } catch (e) { onError(e); }
  };

  const status = (label: string, ok: boolean | null | undefined) => (
    <li className="flex items-center justify-between text-[13px]"><span>{label}</span>
      <span className={ok ? "text-emerald-400" : ok === false ? "text-amber-300" : "text-white/45"}>{ok ? "Ready" : ok === false ? "Not set up" : "Unknown"}</span></li>
  );

  return (
    <ViewShell title="Settings" subtitle="Account, API keys, model routing, voice and data" icon={Settings} onBack={onBack}>
      <div className={`${card} flex items-center justify-between gap-3`}>
        <div>
          <div className="text-[14px]">{user?.display_name}</div>
          <div className="text-xs text-white/55">{user?.is_guest ? "Guest session: chats live in this browser's guest profile only" : user?.email}</div>
        </div>
        <button onClick={logout} className={`${ghost} flex items-center gap-2`}><LogOut size={14} />Log out</button>
      </div>

      <div className={`${card} space-y-3`}>
        <h2 className="text-[14px] font-medium">API keys</h2>
        <p className="text-xs text-white/55">Keys are stored encrypted on the server, are never sent back to the browser, and only the last 4 characters are shown.</p>
        {providers === null ? <p className="text-xs text-white/50">Loading…</p> : providers.map((p) => (
          <ApiKeyCard key={p.id} provider={p} group={models.groups.find((g) => g.id === p.id)} onChanged={keysChanged} onError={onError} />
        ))}
      </div>

      <div className={`${card} space-y-3`}>
        <h2 className="text-[14px] font-medium">Model routing</h2>
        <label className="block text-[13px]">Default model
          <select value={models.selected} onChange={(e) => models.select(e.target.value)} className={`${input} mt-1 !w-auto min-w-[260px]`} aria-label="Default model">
            <option value="auto">Auto (cloud-first){models.auto?.ref ? ` · now ${models.auto.label}` : ""}</option>
            {models.groups.map((g) => (
              <optgroup key={g.id} label={g.label}>
                {g.models.map((m) => <option key={m.ref} value={m.ref} disabled={!USABLE.has(m.state)}>{m.label}{USABLE.has(m.state) ? "" : ` (${m.state.replace("_", " ")})`}</option>)}
              </optgroup>
            ))}
          </select>
        </label>
        <Toggle on={fallback} onChange={onFallback} label="Automatic fallback"
          hint="If a provider is rate-limited, times out or is down before answering, try the next one. Order: DeepSeek → Gemini → local Ollama. You are told whenever a switch happens, and a switch to a slow local model is flagged." />
        <p className="text-[11px] text-white/45">Your manual choice always goes first. Retired model IDs can be replaced on the server with SYNAPTO_DEEPSEEK_CHAT_MODEL, SYNAPTO_GEMINI_PRO_MODEL and similar variables.</p>
        <h3 className="pt-1 text-xs uppercase tracking-wide text-white/50">Optional local models</h3>
        <ul className="space-y-2">
          {RECOMMENDED.map((r) => (
            <li key={r.cmd} className="flex flex-wrap items-center gap-2">
              <Cmd cmd={r.cmd} /><span className="text-xs text-white/60">{r.why}</span>
              {installed(r.match) && <span className="text-[11px] text-emerald-400">installed</span>}
            </li>
          ))}
        </ul>
      </div>

      <div className={`${card} space-y-3`}>
        <h2 className="text-[14px] font-medium">Voice</h2>
        <label className="block text-[13px]">Speech recognition language
          <select value={speechLang} onChange={(e) => onSpeechLang(e.target.value)} className={`${input} mt-1 !w-auto min-w-[220px]`}>
            {SPEECH_LANGS.map(([c, n]) => <option key={c} value={c}>{n}</option>)}
          </select>
        </label>
        <p className="text-[11px] text-white/45">Dictation uses your browser&apos;s speech recognition. Depending on the browser, audio may be sent to the browser vendor&apos;s service, and support varies by browser and language.</p>
        {tts.supported ? (
          <div className="flex flex-wrap items-center gap-2">
            <label className="text-[13px]">Reply voice
              <select value={voiceURI ?? ""} onChange={(e) => onVoiceURI(e.target.value)} className={`${input} mt-1 !w-auto min-w-[220px]`}>
                <option value="">Automatic (match the reply language)</option>
                {tts.voices.map((v) => <option key={v.voiceURI} value={v.voiceURI}>{v.name} ({v.lang})</option>)}
              </select>
            </label>
            <button onClick={() => tts.speak("settings-test", "Hello, this is how Synapto will read replies aloud.")} className={`${ghost} mt-5 flex items-center gap-2`}><Volume2 size={14} />Test voice</button>
          </div>
        ) : <p className="text-xs text-amber-300">This browser doesn&apos;t support speech synthesis, so the Listen button is hidden.</p>}
        {tts.voices.length === 0 && tts.supported && <p className="text-[11px] text-amber-300">No voices are installed in this browser yet. Install system voices for your language.</p>}
      </div>

      <div className={`${card} space-y-2`}>
        <h2 className="text-[14px] font-medium">Reply text size</h2>
        <div className="flex gap-2">
          {[["Small", 0.9], ["Medium", 1], ["Large", 1.2]].map(([label, v]) => (
            <button key={label as string} aria-pressed={scale === v} onClick={() => { setScale(v as number); setReplyScale(v as number); }}
              className={`h-8 rounded-lg border px-3 text-[13px] ${scale === v ? "border-[#8b7bff] bg-brand/25" : "border-line bg-white/[0.04]"}`}>{label}</button>
          ))}
        </div>
      </div>

      <div className={card}>
        <h2 className="mb-1.5 text-[14px] font-medium">Services</h2>
        <ul className="space-y-1">
          {status(`Document embeddings (${caps?.embeddings.model ?? "bge-m3"}, local Ollama)`, caps?.embeddings.installed)}
          {status("Local speech-to-text fallback (Whisper)", caps?.voice.available)}
          {status("Web search (SearXNG)", caps?.web_search.available)}
          {status("Image generation (Stable Diffusion)", caps?.image_generation.available)}
        </ul>
      </div>

      <div className={`${card} flex flex-wrap gap-2`}>
        <button onClick={doExport} className={`${ghost} flex items-center gap-2`}><Download size={14} />Export chats (JSON)</button>
        <button onClick={wipe} className={`${ghost} flex items-center gap-2 text-red-300`}><Trash2 size={14} />Delete all chats</button>
      </div>
    </ViewShell>
  );
}
