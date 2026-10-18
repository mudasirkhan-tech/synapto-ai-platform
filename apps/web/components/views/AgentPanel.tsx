"use client";
import { AlertTriangle, Check, CheckCircle2, Loader2, Play, RotateCcw, Square, Trash2, Wrench, X, XCircle } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import {
  cancelAgentTask, createAgentTask, decideAgentTask, deleteAgentTask, getAgentTask, listAgentTasks, listAgentTools,
} from "@/lib/api";
import type { AgentStatus, AgentStep, AgentTask, AgentToolInfo, Capabilities } from "@/lib/api";
import { scriptClass } from "@/lib/text";
import MarkdownView from "../MarkdownView";
import { card, ghost, input, primary } from "./ViewShell";

const ACTIVE: AgentStatus[] = ["queued", "running", "waiting_approval"];

const BADGE: Record<AgentStatus, { label: string; cls: string }> = {
  queued: { label: "Queued", cls: "text-white/70 border-line" },
  running: { label: "Running", cls: "text-sky-300 border-sky-500/40" },
  waiting_approval: { label: "Needs approval", cls: "text-amber-300 border-amber-500/50" },
  completed: { label: "Done", cls: "text-emerald-300 border-emerald-500/40" },
  failed: { label: "Failed", cls: "text-red-300 border-red-500/40" },
  cancelled: { label: "Cancelled", cls: "text-white/60 border-line" },
};

function Badge({ status }: { status: AgentStatus }) {
  const b = BADGE[status];
  return (
    <span className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] ${b.cls}`}>
      {status === "running" && <Loader2 size={10} className="animate-spin" />}{b.label}
    </span>
  );
}

function argsText(args: Record<string, unknown> | null) {
  return args ? Object.entries(args).map(([k, v]) => `${k}: ${typeof v === "string" ? v : JSON.stringify(v)}`).join(", ") : "";
}

function StepRow({ step, canDecide, onDecide }: { step: AgentStep; canDecide: boolean; onDecide: (approve: boolean) => void }) {
  if (step.kind === "info") return <li className="text-[11px] text-white/40">{step.content}</li>;
  if (step.kind === "note") return <li className="text-[11px] italic text-white/45">The model's reply needed a fix, retrying: {step.content}</li>;
  if (step.kind === "error") return <li className="flex items-center gap-1.5 text-[13px] text-red-300"><XCircle size={14} />{step.content}</li>;
  if (step.kind === "final") {
    return (
      <li className="rounded-lg border border-emerald-500/30 bg-emerald-500/5 p-3">
        <div className="mb-1 flex items-center gap-1.5 text-xs text-emerald-300"><CheckCircle2 size={14} />Final answer</div>
        <MarkdownView content={step.content} />
      </li>
    );
  }
  if (step.kind === "tool_result") {
    return (
      <li>
        <details className="rounded-lg border border-line bg-white/[0.03] px-3 py-1.5 text-xs">
          <summary className="cursor-pointer select-none text-white/70">Result from <b>{step.tool}</b></summary>
          <pre dir="auto" className="thin-scroll mt-1.5 max-h-48 overflow-auto whitespace-pre-wrap break-words text-white/75">{step.content}</pre>
        </details>
      </li>
    );
  }
  // tool_call
  const pending = step.status === "pending_approval";
  return (
    <li className={`rounded-lg border p-2.5 ${pending ? "border-amber-500/50 bg-amber-500/10" : "border-line bg-white/[0.03]"}`}>
      <div className="flex flex-wrap items-center gap-2 text-[13px]">
        <Wrench size={14} className="text-brand-soft" /><b>{step.tool}</b>
        {step.status === "denied" && <span className="text-[11px] text-red-300">denied</span>}
        {step.status === "running" && <Loader2 size={12} className="animate-spin text-white/60" />}
      </div>
      {step.content && <p dir="auto" className="mt-0.5 text-xs text-white/60">{step.content}</p>}
      {step.args && (
        <pre dir="auto" className="thin-scroll mt-1 max-h-32 overflow-auto whitespace-pre-wrap break-words text-[11px] text-white/55">{argsText(step.args)}</pre>
      )}
      {pending && canDecide && (
        <div className="mt-2 flex items-center gap-2">
          <span className="flex items-center gap-1 text-xs text-amber-200"><AlertTriangle size={13} />This action changes your data. Allow it?</span>
          <button onClick={() => onDecide(true)} className="ml-auto flex h-8 items-center gap-1.5 rounded-lg bg-emerald-600 px-3 text-xs hover:bg-emerald-500"><Check size={13} />Approve</button>
          <button onClick={() => onDecide(false)} className="flex h-8 items-center gap-1.5 rounded-lg border border-line px-3 text-xs hover:bg-white/5"><X size={13} />Deny</button>
        </div>
      )}
    </li>
  );
}

export default function AgentPanel({ model, caps, onError }: { model: string | null; caps: Capabilities | null; onError: (e: unknown) => void }) {
  const [goal, setGoal] = useState("");
  const [useDocs, setUseDocs] = useState(false);
  const [useWeb, setUseWeb] = useState(false);
  const [tools, setTools] = useState<AgentToolInfo[]>([]);
  const [tasks, setTasks] = useState<AgentTask[]>([]);
  const [current, setCurrent] = useState<AgentTask | null>(null);
  const [busy, setBusy] = useState(false);
  const webReady = caps?.web_search.available ?? false;

  const loadList = useCallback(() => { listAgentTasks().then(setTasks).catch(onError); }, [onError]);
  useEffect(() => { loadList(); listAgentTools().then(setTools).catch(onError); }, [loadList, onError]);

  // Poll the open task while it is active so progress appears step by step.
  const currentId = current?.id;
  const active = current ? ACTIVE.includes(current.status) : false;
  useEffect(() => {
    if (!currentId || !active) return;
    const t = setInterval(() => {
      getAgentTask(currentId).then((task) => { setCurrent(task); if (!ACTIVE.includes(task.status)) loadList(); }).catch(onError);
    }, 1200);
    return () => clearInterval(t);
  }, [currentId, active, loadList, onError]);

  const start = async (g: string, docs: boolean, web: boolean) => {
    setBusy(true);
    try {
      const task = await createAgentTask({ goal: g, model: model ?? undefined, use_knowledge: docs, web_search: web });
      setCurrent(task); setGoal(""); loadList();
    } catch (e) { onError(e); } finally { setBusy(false); }
  };

  const act = async (fn: () => Promise<AgentTask>) => {
    try { setCurrent(await fn()); loadList(); } catch (e) { onError(e); }
  };

  const toggle = (on: boolean, set: (v: boolean) => void, label: string, disabled = false, hint = "") => (
    <label title={hint} className={`flex items-center gap-2 text-[13px] ${disabled ? "opacity-50" : ""}`}>
      <input type="checkbox" checked={on} disabled={disabled} onChange={(e) => set(e.target.checked)} />{label}
    </label>
  );

  return (
    <div className="space-y-3">
      <div className={`${card} space-y-2.5`}>
        <textarea dir="auto" value={goal} onChange={(e) => setGoal(e.target.value)} rows={3} maxLength={2000}
          placeholder="Describe a goal, e.g. “Convert 26.2 miles to km and what is 15% of the result?”"
          className={`${input} resize-none ${scriptClass(goal)}`} />
        <div className="flex flex-wrap items-center gap-4">
          {toggle(useDocs, setUseDocs, "Use my documents")}
          {toggle(useWeb, setUseWeb, "Use web search", !webReady, webReady ? "" : "Web search isn't configured")}
          <button onClick={() => start(goal.trim(), useDocs, useWeb)} disabled={busy || !goal.trim()} className={`${primary} ml-auto flex items-center gap-2`}>
            {busy ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />}Run agent
          </button>
        </div>
        <div className="flex flex-wrap gap-1.5 pt-0.5">
          {tools.map((t) => (
            <span key={t.name} title={`${t.description}${t.note ? ` (${t.note})` : ""}`}
              className={`rounded-full border px-2 py-0.5 text-[11px] ${t.requires_approval ? "border-amber-500/40 text-amber-200" : "border-line text-white/60"} ${t.available ? "" : "opacity-40"}`}>
              {t.name}{t.requires_approval ? " · asks first" : ""}
            </span>
          ))}
        </div>
        <p className="text-[11px] text-white/40">Bounded to a few steps. Tool results are treated as untrusted data. Anything that changes your data waits for your approval.</p>
      </div>

      {current && (
        <div className={`${card} space-y-2.5`}>
          <div className="flex flex-wrap items-center gap-2">
            <Badge status={current.status} />
            <span dir="auto" className="min-w-0 flex-1 truncate text-[13px]">{current.goal}</span>
            {ACTIVE.includes(current.status) && (
              <button onClick={() => act(() => cancelAgentTask(current.id))} className={`${ghost} flex !h-8 items-center gap-1.5 text-xs`}><Square size={12} />Cancel</button>
            )}
            {!ACTIVE.includes(current.status) && (
              <button onClick={() => start(current.goal, current.use_knowledge, current.web_search)} disabled={busy} className={`${ghost} flex !h-8 items-center gap-1.5 text-xs`}><RotateCcw size={12} />Retry</button>
            )}
          </div>
          <ol className="space-y-2">
            {current.steps.map((s) => (
              <StepRow key={s.id} step={s} canDecide={current.status === "waiting_approval"}
                onDecide={(approve) => act(() => decideAgentTask(current.id, approve))} />
            ))}
          </ol>
          {current.status === "running" && <p className="flex items-center gap-1.5 text-xs text-white/50"><Loader2 size={12} className="animate-spin" />Working…</p>}
        </div>
      )}

      {tasks.length > 0 && (
        <div className={card}>
          <h3 className="mb-1.5 text-xs uppercase tracking-wide text-white/50">Recent tasks</h3>
          <ul className="space-y-1">
            {tasks.map((t) => (
              <li key={t.id} className="group flex items-center gap-2">
                <button onClick={() => getAgentTask(t.id).then(setCurrent).catch(onError)}
                  className={`flex min-w-0 flex-1 items-center gap-2 rounded-lg px-2 py-1.5 text-left hover:bg-white/5 ${current?.id === t.id ? "bg-white/[0.07]" : ""}`}>
                  <Badge status={t.status} /><span dir="auto" className="truncate text-[13px] text-white/80">{t.goal}</span>
                </button>
                {!ACTIVE.includes(t.status) || t.status === "waiting_approval" ? (
                  <button aria-label="Delete task" onClick={() => deleteAgentTask(t.id).then(() => { if (current?.id === t.id) setCurrent(null); loadList(); }).catch(onError)}
                    className="rounded p-1 text-white/40 opacity-0 hover:text-red-400 focus-visible:opacity-100 group-hover:opacity-100"><Trash2 size={14} /></button>
                ) : null}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
