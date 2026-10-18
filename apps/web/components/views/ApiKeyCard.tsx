"use client";
import { CheckCircle2, Eye, EyeOff, KeyRound, Loader2, Trash2 } from "lucide-react";
import { useState } from "react";
import { deleteProviderKey, saveProviderKey, testProvider } from "@/lib/api";
import type { CatalogGroup, ProviderInfo } from "@/lib/api";
import { ghost, input, primary } from "./ViewShell";

const HELP: Record<string, string> = {
  deepseek: "Get a key at platform.deepseek.com. Usage is billed by DeepSeek.",
  gemini: "Get a key in Google AI Studio (aistudio.google.com). A free tier may apply.",
};

/** Write-only key form: the key is sent once over your session, stored encrypted on the server, and never shown again. */
export default function ApiKeyCard({ provider, group, onChanged, onError }: {
  provider: ProviderInfo; group?: CatalogGroup; onChanged: () => void; onError: (e: unknown) => void;
}) {
  const [value, setValue] = useState("");
  const [show, setShow] = useState(false);
  const [busy, setBusy] = useState<"save" | "test" | "delete" | null>(null);
  const [result, setResult] = useState<{ ok: boolean; text: string } | null>(null);

  const run = async (kind: "save" | "test" | "delete", fn: () => Promise<void>) => {
    setBusy(kind); setResult(null);
    try { await fn(); } catch (e) { setResult({ ok: false, text: e instanceof Error ? e.message : "Something went wrong." }); } finally { setBusy(null); }
  };

  const status = !provider.configured ? { text: "Not configured", cls: "text-white/50" }
    : group?.status === "auth_error" ? { text: "Key rejected", cls: "text-red-300" }
    : group?.status === "billing" ? { text: "No balance", cls: "text-red-300" }
    : group?.status === "ok" ? { text: "Connected", cls: "text-emerald-400" }
    : { text: "Configured (not verified)", cls: "text-amber-300" };

  return (
    <div className="rounded-xl border border-line bg-white/[0.02] p-3">
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <KeyRound size={15} className="text-brand-soft" />
        <span className="text-[14px] font-medium">{provider.label}</span>
        <span className={`text-xs ${status.cls}`}>{status.text}</span>
        {provider.masked && <code className="ml-auto text-xs text-white/60">{provider.masked}{provider.source === "server" ? " · server environment" : ""}</code>}
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <div className="relative min-w-[200px] flex-1">
          <input type={show ? "text" : "password"} value={value} onChange={(e) => setValue(e.target.value)} autoComplete="off" spellCheck={false}
            aria-label={`${provider.label} API key`} placeholder={provider.configured ? "Enter a new key to replace it" : "Paste your API key"} className={`${input} pr-9 font-mono`} />
          <button type="button" onClick={() => setShow((s) => !s)} aria-label={show ? "Hide key" : "Show key"} className="absolute right-2 top-1/2 -translate-y-1/2 text-white/55 hover:text-white">
            {show ? <EyeOff size={15} /> : <Eye size={15} />}
          </button>
        </div>
        <button disabled={!value.trim() || busy !== null} className={`${primary} !h-9`} onClick={() => run("save", async () => {
          await saveProviderKey(provider.id, value.trim());
          setValue(""); setShow(false); setResult({ ok: true, text: "Saved. The key is stored encrypted on the server." }); onChanged();
        })}>{busy === "save" ? <Loader2 size={14} className="animate-spin" /> : "Save"}</button>
        <button disabled={(!value.trim() && !provider.configured) || busy !== null} className={ghost} onClick={() => run("test", async () => {
          const r = await testProvider(provider.id, value.trim() || undefined);
          setResult({ ok: r.ok, text: r.message });
        })}>{busy === "test" ? <Loader2 size={14} className="animate-spin" /> : "Test connection"}</button>
        {provider.source === "user" && (
          <button disabled={busy !== null} aria-label={`Delete ${provider.label} key`} className={`${ghost} text-red-300`} onClick={() => run("delete", async () => {
            await deleteProviderKey(provider.id); setResult({ ok: true, text: "Key deleted." }); onChanged();
          })}><Trash2 size={14} /></button>
        )}
      </div>
      {result && (
        <p role="status" className={`mt-2 flex items-start gap-1.5 text-xs ${result.ok ? "text-emerald-300" : "text-red-300"}`}>
          {result.ok && <CheckCircle2 size={13} className="mt-0.5 shrink-0" />}{result.text}
        </p>
      )}
      <p className="mt-2 text-[11px] text-white/40">{HELP[provider.id]} You can also set <code>{provider.env_var}</code> on the server instead.</p>
    </div>
  );
}
