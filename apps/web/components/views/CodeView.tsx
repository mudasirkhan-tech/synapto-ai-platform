"use client";
import { Code2, Send } from "lucide-react";
import { useState } from "react";
import type { CatalogModel } from "@/lib/api";
import ViewShell, { card, ghost, input, primary } from "./ViewShell";

const LANGS = ["Python", "JavaScript", "TypeScript", "Java", "C++", "C#", "Go", "Rust", "SQL", "Bash", "HTML/CSS", "Other"];
const TASKS: Record<string, string> = {
  Explain: "Explain what this code does, step by step.",
  Debug: "Find the bug(s) in this code, explain the cause, and give the corrected code.",
  Refactor: "Refactor this code for readability and maintainability without changing behaviour.",
  "Write tests": "Write unit tests for this code, covering normal and edge cases.",
  Review: "Review this code: correctness, security, performance and style. List concrete improvements.",
  Convert: "Convert this code to the language named in the notes below.",
};

export default function CodeView({ models, selected, onSelectModel, onBack, onSend }: {
  models: CatalogModel[]; selected: string; onSelectModel: (ref: string) => void; onBack: () => void; onSend: (prompt: string) => void;
}) {
  const [lang, setLang] = useState("Python");
  const [task, setTask] = useState("Explain");
  const [code, setCode] = useState("");
  const [notes, setNotes] = useState("");
  const coder = models.find((m) => m.tags.includes("code"));

  const send = () => {
    const fence = lang === "Other" ? "" : lang.toLowerCase().replace("c++", "cpp").replace("c#", "csharp").replace("html/css", "html");
    const body = code.trim() ? `\n\n\`\`\`${fence}\n${code.trim()}\n\`\`\`` : "";
    onSend(`${TASKS[task]}${body}${notes.trim() ? `\n\nNotes: ${notes.trim()}` : ""}`);
  };

  return (
    <ViewShell title="Code Assistant" subtitle="Explain, debug, refactor, test and review. Code is never executed." icon={Code2} onBack={onBack}>
      <div className={`${card} space-y-3`}>
        <div className="flex flex-wrap gap-1.5" role="tablist" aria-label="Task">
          {Object.keys(TASKS).map((t) => (
            <button key={t} role="tab" aria-selected={task === t} onClick={() => setTask(t)}
              className={`h-8 rounded-lg border px-3 text-[13px] ${task === t ? "border-[#8b7bff] bg-brand/25" : "border-line bg-white/[0.04] hover:bg-white/[0.08]"}`}>{t}</button>
          ))}
        </div>
        <div className="flex items-center gap-2.5">
          <select value={lang} onChange={(e) => setLang(e.target.value)} className={`${input} !w-auto`} aria-label="Language">
            {LANGS.map((l) => <option key={l}>{l}</option>)}
          </select>
          {coder && selected !== coder.ref && (
            <button onClick={() => onSelectModel(coder.ref)} className={ghost}>Use {coder.label} (code model)</button>
          )}
        </div>
        <textarea dir="ltr" value={code} onChange={(e) => setCode(e.target.value)} rows={11} spellCheck={false}
          placeholder="Paste your code or error message here…" className={`${input} resize-none font-mono text-[12.5px]`} />
        <input dir="auto" value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="Notes (optional): what you expect, constraints, target language…" className={input} />
        <div className="flex justify-end">
          <button onClick={send} disabled={!code.trim() && !notes.trim()} className={`${primary} flex items-center gap-2`}><Send size={14} />Send to chat</button>
        </div>
      </div>
    </ViewShell>
  );
}
