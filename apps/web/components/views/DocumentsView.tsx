"use client";
import { FolderOpen, Loader2, RefreshCw, Trash2, Upload } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { deleteDocument, listDocuments, reindexDocument, uploadDocument } from "@/lib/api";
import type { Capabilities, DocumentInfo } from "@/lib/api";
import ViewShell, { SetupNotice, card, primary } from "./ViewShell";

export default function DocumentsView({ caps, onBack, onError }: { caps: Capabilities | null; onBack: () => void; onError: (e: unknown) => void }) {
  const [docs, setDocs] = useState<DocumentInfo[]>([]);
  const [busy, setBusy] = useState(false);
  const picker = useRef<HTMLInputElement>(null);

  const load = useCallback(() => { listDocuments("library").then(setDocs).catch(onError); }, [onError]);
  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    if (!docs.some((d) => d.status === "processing")) return;
    const t = setInterval(load, 2000);
    return () => clearInterval(t);
  }, [docs, load]);

  const upload = async (files: FileList | null) => {
    if (!files?.length) return;
    setBusy(true);
    for (const f of Array.from(files)) {
      try { await uploadDocument(f, "library"); } catch (e) { onError(e); }
    }
    setBusy(false);
    if (picker.current) picker.current.value = "";
    load();
  };

  return (
    <ViewShell title="Documents" subtitle="Your private knowledge base: indexed locally, searchable from chat" icon={FolderOpen} onBack={onBack}>
      {caps?.embeddings.installed === false && (
        <SetupNotice title="Embedding model not installed" text={`Documents will use keyword search only until you run: ${caps.embeddings.setup}, then press Re-index.`} />
      )}
      <div className={`${card} flex items-center justify-between gap-3`}>
        <p className="text-[13px] text-white/70">PDF, DOCX, TXT, MD, CSV, JSON · up to 25 MB each. Turn on the book icon in the chat box to search these files.</p>
        <input ref={picker} type="file" multiple hidden accept=".pdf,.docx,.txt,.md,.csv,.json" onChange={(e) => upload(e.target.files)} />
        <button onClick={() => picker.current?.click()} disabled={busy} className={`${primary} flex shrink-0 items-center gap-2`}>
          {busy ? <Loader2 size={14} className="animate-spin" /> : <Upload size={14} />}Add files
        </button>
      </div>

      {docs.length === 0 ? <p className="px-1 text-[13px] text-white/50">No documents yet.</p> : (
        <ul className="space-y-2">
          {docs.map((d) => (
            <li key={d.id} className={`${card} flex items-center gap-3`}>
              <div className="min-w-0 flex-1">
                <div dir="auto" className="truncate text-[13px]">{d.filename}</div>
                <div className="mt-0.5 flex flex-wrap items-center gap-2 text-[11px] text-white/55">
                  {d.status === "processing" && <span className="flex items-center gap-1"><Loader2 size={11} className="animate-spin" />Indexing…</span>}
                  {d.status === "ready" && <span className="text-emerald-400">Ready</span>}
                  {d.status === "failed" && <span className="text-red-300">Failed</span>}
                  {d.status === "ready" && <span>{d.chunk_count} passages · {d.embedded ? "semantic + keyword search" : "keyword search only"}</span>}
                </div>
                {d.error && <div className="mt-0.5 text-[11px] text-amber-200/90">{d.error}</div>}
              </div>
              {d.status === "ready" && !d.embedded && (
                <button onClick={() => reindexDocument(d.id).then(() => setTimeout(load, 1500)).catch(onError)} className="flex items-center gap-1 rounded-lg border border-line px-2.5 py-1.5 text-xs hover:bg-white/5">
                  <RefreshCw size={12} />Re-index
                </button>
              )}
              <button aria-label={`Delete ${d.filename}`} onClick={() => deleteDocument(d.id).then(load).catch(onError)} className="rounded-lg p-1.5 text-white/55 hover:bg-white/5 hover:text-red-400"><Trash2 size={15} /></button>
            </li>
          ))}
        </ul>
      )}
    </ViewShell>
  );
}
