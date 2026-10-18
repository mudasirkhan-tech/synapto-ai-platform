"use client";
import { ArrowRightLeft, Calculator, Wrench } from "lucide-react";
import { useEffect, useState } from "react";
import { calculate, convertUnits, unitCatalog } from "@/lib/api";
import type { Capabilities } from "@/lib/api";
import AgentPanel from "./AgentPanel";
import ViewShell, { card, input, primary } from "./ViewShell";

export default function ToolsView({ onBack, model, caps, onError }: {
  onBack: () => void; model: string | null; caps: Capabilities | null; onError: (e: unknown) => void;
}) {
  const [tab, setTab] = useState<"agent" | "calc">("agent");
  const [expr, setExpr] = useState("");
  const [calcOut, setCalcOut] = useState<{ ok: boolean; text: string } | null>(null);
  const [history, setHistory] = useState<string[]>([]);

  const [units, setUnits] = useState<Record<string, string[]>>({});
  const [category, setCategory] = useState("length");
  const [value, setValue] = useState("1");
  const [from, setFrom] = useState("m");
  const [to, setTo] = useState("ft");
  const [convOut, setConvOut] = useState<{ ok: boolean; text: string } | null>(null);

  useEffect(() => { unitCatalog().then(setUnits).catch(() => {}); }, []);

  const runCalc = async () => {
    if (!expr.trim()) return;
    try {
      const r = await calculate(expr);
      setCalcOut({ ok: true, text: String(r.result) });
      setHistory((h) => [`${expr} = ${r.result}`, ...h].slice(0, 5));
    } catch (e) { setCalcOut({ ok: false, text: e instanceof Error ? e.message : "Error" }); }
  };

  const pickCategory = (c: string) => { setCategory(c); const list = units[c] ?? []; setFrom(list[0] ?? ""); setTo(list[1] ?? list[0] ?? ""); setConvOut(null); };

  const runConvert = async () => {
    const n = Number(value);
    if (!Number.isFinite(n)) { setConvOut({ ok: false, text: "Enter a number" }); return; }
    try {
      const r = await convertUnits(n, from, to);
      setConvOut({ ok: true, text: `${n} ${from} = ${Number(r.result.toPrecision(10))} ${to}` });
    } catch (e) { setConvOut({ ok: false, text: e instanceof Error ? e.message : "Error" }); }
  };

  const list = units[category] ?? [];

  return (
    <ViewShell title="Tools" subtitle="Agent workflows and deterministic tools" icon={Wrench} onBack={onBack}>
      <div role="tablist" aria-label="Tools" className="flex gap-1.5">
        {([["agent", "Agent workflows"], ["calc", "Calculator & units"]] as const).map(([id, label]) => (
          <button key={id} role="tab" aria-selected={tab === id} onClick={() => setTab(id)}
            className={`h-8 rounded-lg border px-3 text-[13px] ${tab === id ? "border-[#8b7bff] bg-brand/25" : "border-line bg-white/[0.04] hover:bg-white/[0.08]"}`}>{label}</button>
        ))}
      </div>
      {tab === "agent" && <AgentPanel model={model} caps={caps} onError={onError} />}
      {tab === "calc" && <>
      <div className={`${card} space-y-2.5`}>
        <h2 className="flex items-center gap-2 text-[14px] font-medium"><Calculator size={16} className="text-brand-soft" />Calculator</h2>
        <div className="flex gap-2">
          <input dir="ltr" value={expr} onChange={(e) => setExpr(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter") runCalc(); }}
            placeholder="e.g. sqrt(144) + 2**10 / 4" className={`${input} font-mono`} />
          <button onClick={runCalc} className={primary}>=</button>
        </div>
        {calcOut && <p role="status" className={`text-[15px] ${calcOut.ok ? "text-emerald-300" : "text-red-300"}`}>{calcOut.text}</p>}
        {history.length > 0 && <ul className="space-y-0.5 text-xs text-white/50">{history.map((h, i) => <li key={i} dir="ltr" className="font-mono">{h}</li>)}</ul>}
        <p className="text-[11px] text-white/40">Supports + − × ÷ // % **, parentheses, pi, e, sqrt, sin, cos, tan, log, exp, abs, round, min, max.</p>
      </div>

      <div className={`${card} space-y-2.5`}>
        <h2 className="flex items-center gap-2 text-[14px] font-medium"><ArrowRightLeft size={16} className="text-brand-soft" />Unit converter</h2>
        <div className="flex flex-wrap items-center gap-2">
          <select value={category} onChange={(e) => pickCategory(e.target.value)} className={`${input} !w-auto`} aria-label="Category">
            {Object.keys(units).map((c) => <option key={c}>{c}</option>)}
          </select>
          <input dir="ltr" value={value} onChange={(e) => setValue(e.target.value)} inputMode="decimal" className={`${input} !w-28`} aria-label="Value" />
          <select value={from} onChange={(e) => setFrom(e.target.value)} className={`${input} !w-auto`} aria-label="From unit">{list.map((u) => <option key={u}>{u}</option>)}</select>
          <span className="text-white/50">→</span>
          <select value={to} onChange={(e) => setTo(e.target.value)} className={`${input} !w-auto`} aria-label="To unit">{list.map((u) => <option key={u}>{u}</option>)}</select>
          <button onClick={runConvert} className={primary}>Convert</button>
        </div>
        {convOut && <p role="status" className={`text-[15px] ${convOut.ok ? "text-emerald-300" : "text-red-300"}`}>{convOut.text}</p>}
      </div>
      </>}
    </ViewShell>
  );
}
