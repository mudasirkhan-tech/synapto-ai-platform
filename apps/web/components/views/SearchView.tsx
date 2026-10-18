"use client";
import { ExternalLink, Globe, Loader2, Search } from "lucide-react";
import { useState } from "react";
import { webSearch } from "@/lib/api";
import type { Capabilities, WebResult } from "@/lib/api";
import { scriptClass } from "@/lib/text";
import ViewShell, { SetupNotice, card, input, primary } from "./ViewShell";

export default function SearchView({ caps, onBack, onError, onAsk }: {
  caps: Capabilities | null; onBack: () => void; onError: (e: unknown) => void; onAsk: (query: string) => void;
}) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<WebResult[] | null>(null);
  const [busy, setBusy] = useState(false);
  const available = caps?.web_search.available ?? false;

  const run = async () => {
    if (!query.trim()) return;
    setBusy(true);
    try { setResults(await webSearch(query.trim())); } catch (e) { onError(e); } finally { setBusy(false); }
  };

  return (
    <ViewShell title="Web Search" subtitle="Self-hosted search (SearXNG): no API keys, results are cited in answers" icon={Globe} onBack={onBack}>
      {caps && !available && <SetupNotice title="Web search isn't set up" text={caps.web_search.setup} />}
      <div className={`${card} flex gap-2`}>
        <input dir="auto" value={query} onChange={(e) => setQuery(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter") run(); }}
          placeholder="Search the web…" maxLength={300} className={`${input} ${scriptClass(query)}`} />
        <button onClick={run} disabled={!available || busy || !query.trim()} className={`${primary} flex items-center gap-2`}>
          {busy ? <Loader2 size={14} className="animate-spin" /> : <Search size={14} />}Search
        </button>
      </div>

      {results && (
        <>
          <div className="flex items-center justify-between">
            <span className="text-xs text-white/60">{results.length} result{results.length === 1 ? "" : "s"}</span>
            {results.length > 0 && <button onClick={() => onAsk(query.trim())} className={`${primary}`}>Ask Synapto using these results</button>}
          </div>
          <ul className="space-y-2">
            {results.map((r) => (
              <li key={r.url} className={card}>
                <a href={r.url} target="_blank" rel="noopener noreferrer" dir="auto" className="flex items-center gap-1.5 text-[14px] text-brand-soft hover:underline">
                  <span className="truncate">{r.title}</span><ExternalLink size={12} className="shrink-0" />
                </a>
                <div className="truncate text-[11px] text-white/40">{r.url}</div>
                <p dir="auto" className="mt-1 text-[13px] text-white/75">{r.snippet}</p>
              </li>
            ))}
          </ul>
        </>
      )}
    </ViewShell>
  );
}
