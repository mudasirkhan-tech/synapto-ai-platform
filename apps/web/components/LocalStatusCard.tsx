"use client";
import { AlertTriangle, CheckCircle2, Loader2, MinusCircle, XCircle, Zap } from "lucide-react";
import type { ModelsState } from "@/lib/useModels";
import { useSystemStatus } from "@/lib/useSystemStatus";

type Tone = "ok" | "bad" | "wait" | "off";

function Row({ tone, label, detail }: { tone: Tone; label: string; detail?: string }) {
  const icon =
    tone === "ok" ? <CheckCircle2 size={15} className="text-emerald-400" /> :
    tone === "bad" ? <XCircle size={15} className="text-red-400" /> :
    tone === "off" ? <MinusCircle size={15} className="text-white/40" /> :
    <Loader2 size={15} className="animate-spin text-white/60" />;
  return (
    <li className="flex items-start gap-2 text-[13px]">
      <span className="mt-0.5">{icon}</span>
      <span>{label}{detail && <span className="block text-[11px] leading-tight text-white/60">{detail}</span>}</span>
    </li>
  );
}

const GROUP_TONE: Record<string, Tone> = { ok: "ok", unverified: "wait", no_key: "off", auth_error: "bad", billing: "bad", unreachable: "off" };

export default function LocalStatusCard({ models }: { models: ModelsState }) {
  const s = useSystemStatus();
  const { auto, groups, selected, activeLabel, loading } = models;

  return (
    <section aria-live="polite" className="relative overflow-hidden rounded-2xl border border-line bg-gradient-to-br from-card to-[#14102b] p-3">
      <div className="mb-2 flex items-center gap-2.5">
        <Zap size={26} className="fill-amber-400 text-amber-400" />
        <div className="leading-tight">
          <div className="text-[11px] text-amber-300">Powered by</div>
          <div className="text-[15px] font-semibold text-sky-300">Cloud + Local AI</div>
        </div>
        {s.phase === "api-down" && <AlertTriangle size={15} className="ml-auto text-amber-400" />}
      </div>
      <ul className="space-y-1.5">
        {s.phase === "loading" && <Row tone="wait" label="SYNAPTO API" detail="Checking…" />}
        {s.phase === "api-down" && <Row tone="bad" label="SYNAPTO API offline" detail="Start it: uv run uvicorn app.main:app --port 8000" />}
        {s.phase === "ready" && <Row tone="ok" label="SYNAPTO API online" detail={`v${s.data.api.version}`} />}
        {s.phase === "ready" && (
          <Row tone={auto?.ref || selected !== "auto" ? "ok" : loading ? "wait" : "bad"} label={`Active: ${activeLabel}`}
            detail={selected === "auto" ? (auto?.note || "Cloud-first routing") : "Manual selection"} />
        )}
        {s.phase === "ready" && groups.map((g) => (
          <Row key={g.id} tone={GROUP_TONE[g.status] ?? "wait"} label={g.cloud ? g.label.charAt(0) + g.label.slice(1).toLowerCase() : "Ollama (local)"}
            detail={g.id === "ollama" ? (g.status === "ok" ? `${g.models.length} model${g.models.length === 1 ? "" : "s"} installed` : g.detail) : g.detail} />
        ))}
      </ul>
    </section>
  );
}
