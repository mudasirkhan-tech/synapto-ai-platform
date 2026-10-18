"use client";
import { Check, ChevronDown, Cloud, Cpu, Loader2, Sparkles } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import type { ModelsState } from "@/lib/useModels";
import { USABLE } from "@/lib/useModels";

const STATE_LABEL: Record<string, { text: string; cls: string }> = {
  ready: { text: "", cls: "" },
  unverified: { text: "unverified", cls: "text-amber-300" },
  needs_key: { text: "add key", cls: "text-white/45" },
  auth_error: { text: "key rejected", cls: "text-red-300" },
  billing: { text: "no balance", cls: "text-red-300" },
  unavailable: { text: "not offered", cls: "text-red-300" },
};
const GROUP_STATUS: Record<string, { text: string; cls: string }> = {
  ok: { text: "Connected", cls: "text-emerald-400" },
  unverified: { text: "Not verified", cls: "text-amber-300" },
  no_key: { text: "No API key", cls: "text-white/50" },
  auth_error: { text: "Key rejected", cls: "text-red-300" },
  billing: { text: "No balance", cls: "text-red-300" },
  unreachable: { text: "Not running", cls: "text-red-300" },
};

/** Provider-grouped model picker. Unusable models are shown but disabled, with the reason. */
export default function ModelSelector({ models, disabled }: { models: ModelsState; disabled?: boolean }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const down = (e: MouseEvent) => { if (!ref.current?.contains(e.target as Node)) setOpen(false); };
    const key = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    document.addEventListener("mousedown", down);
    document.addEventListener("keydown", key);
    return () => { document.removeEventListener("mousedown", down); document.removeEventListener("keydown", key); };
  }, [open]);

  const { selected, current, auto, groups, loading, error } = models;
  const problem = current && !USABLE.has(current.state);
  const Icon = selected === "auto" ? Sparkles : current && !groups.find((g) => g.models.includes(current))?.cloud ? Cpu : Cloud;

  return (
    <div ref={ref} className="relative">
      <button
        disabled={disabled}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-label={`Model: ${models.activeLabel}`}
        onClick={() => { if (!open) models.refresh(); setOpen((o) => !o); }}
        className={`flex h-8 max-w-[230px] items-center gap-1.5 rounded-lg border bg-white/[0.04] px-2.5 text-[13px] hover:bg-white/[0.08] disabled:opacity-50 ${problem ? "border-red-500/50" : "border-line"}`}
      >
        {loading && !models.data ? <Loader2 size={14} className="animate-spin text-white/60" /> : <Icon size={14} className={problem ? "text-red-300" : "text-brand-soft"} />}
        <span className="truncate">{models.activeLabel}</span>
        <ChevronDown size={14} className="shrink-0 text-white/60" />
      </button>

      {open && (
        <div role="listbox" aria-label="Models" className="thin-scroll absolute bottom-full left-0 z-30 mb-2 max-h-[min(70vh,26rem)] w-[min(22rem,90vw)] overflow-y-auto rounded-xl border border-line bg-card p-1.5 shadow-2xl">
          {error && (
            <div className="m-1 rounded-lg border border-red-500/40 bg-red-500/10 p-2 text-xs text-red-200">
              Couldn&apos;t load models. {error} <button className="underline" onClick={() => models.refresh()}>Retry</button>
            </div>
          )}

          <button role="option" aria-selected={selected === "auto"} onClick={() => { models.select("auto"); setOpen(false); }}
            className="flex w-full items-start gap-2 rounded-lg px-2.5 py-2 text-left hover:bg-white/[0.07]">
            <Sparkles size={15} className="mt-0.5 text-brand-soft" />
            <span className="min-w-0 flex-1">
              <span className="block text-[13px]">Auto <span className="text-white/45">(cloud-first)</span></span>
              <span className="block text-[11px] text-white/50">{auto?.ref ? `Right now: ${auto.label}` : auto?.note || "Checking…"}</span>
              {auto?.ref && auto.note && <span className="block text-[11px] text-amber-300">{auto.note}</span>}
            </span>
            {selected === "auto" && <Check size={14} className="mt-0.5 text-brand-soft" />}
          </button>

          {models.groups.map((g) => {
            const gs = GROUP_STATUS[g.status] ?? { text: g.status, cls: "text-white/50" };
            return (
              <div key={g.id} className="mt-1.5 border-t border-line pt-1.5">
                <div className="flex items-center gap-1.5 px-2.5 pb-1 text-[10.5px] font-medium tracking-wide text-white/50">
                  {g.cloud ? <Cloud size={12} /> : <Cpu size={12} />}{g.label}
                  <span className={`ml-auto font-normal normal-case ${gs.cls}`} title={g.detail}>{gs.text}</span>
                </div>
                {g.models.length === 0 && <p className="px-2.5 pb-1 text-[11px] text-white/45">{g.detail}{!g.cloud && " Run: ollama pull llama3.2"}</p>}
                {g.models.map((m) => {
                  const usable = USABLE.has(m.state);
                  const st = STATE_LABEL[m.state] ?? { text: m.state, cls: "text-white/50" };
                  return (
                    <button key={m.ref} role="option" aria-selected={selected === m.ref} disabled={!usable} title={m.detail || undefined}
                      onClick={() => { models.select(m.ref); setOpen(false); }}
                      className="flex w-full items-center gap-2 rounded-lg px-2.5 py-1.5 text-left hover:bg-white/[0.07] disabled:cursor-not-allowed disabled:opacity-55 disabled:hover:bg-transparent">
                      <span className={`h-1.5 w-1.5 shrink-0 rounded-full ${m.state === "ready" ? "bg-emerald-400" : m.state === "unverified" ? "bg-amber-300" : "bg-white/25"}`} />
                      <span className="min-w-0 flex-1">
                        <span className="block truncate text-[13px]">{m.label}</span>
                        {!usable && m.detail && <span className="block text-[11px] leading-tight text-white/45">{m.detail}</span>}
                      </span>
                      {m.tags.filter((t) => t !== "local").map((t) => <span key={t} className="rounded bg-white/10 px-1 text-[10px] text-white/70">{t}</span>)}
                      {st.text && <span className={`text-[11px] ${st.cls}`}>{st.text}</span>}
                      {selected === m.ref && <Check size={14} className="text-brand-soft" />}
                    </button>
                  );
                })}
              </div>
            );
          })}
          <p className="mt-1.5 border-t border-line px-2.5 pt-1.5 text-[10.5px] leading-snug text-white/40">
            Cloud models send your messages (and any document excerpts used) to the provider. Local models stay on this computer.
          </p>
        </div>
      )}
    </div>
  );
}
