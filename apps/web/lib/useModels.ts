"use client";
import { useCallback, useEffect, useMemo, useState } from "react";
import { listModels } from "./api";
import type { CatalogModel, ModelsOut } from "./api";

const KEY = "synapto.model";
export const USABLE = new Set(["ready", "unverified"]);

/** Model catalog (DeepSeek / Gemini / Ollama) plus the user's selection. "auto" follows the cloud-first priority. */
export function useModels() {
  const [data, setData] = useState<ModelsOut | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<string>("auto");

  useEffect(() => { const saved = window.localStorage.getItem(KEY); if (saved) setSelected(saved); }, []);

  const refresh = useCallback(async () => {
    setLoading(true);
    try { setData(await listModels()); setError(null); }
    catch (e) { setError(e instanceof Error ? e.message : "Could not load models"); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { refresh(); }, [refresh]);

  const flat: CatalogModel[] = useMemo(() => data?.groups.flatMap((g) => g.models) ?? [], [data]);

  // Normalise old saved values (Phase 3 stored bare Ollama names) and drop selections that no longer exist.
  useEffect(() => {
    if (!data || selected === "auto") return;
    if (flat.some((m) => m.ref === selected)) return;
    const legacy = flat.find((m) => m.ref === `ollama:${selected}`);
    const next = legacy ? legacy.ref : "auto";
    setSelected(next);
    window.localStorage.setItem(KEY, next);
  }, [data, flat, selected]);

  const select = useCallback((ref: string) => { setSelected(ref); window.localStorage.setItem(KEY, ref); }, []);

  const current = selected === "auto" ? null : flat.find((m) => m.ref === selected) ?? null;
  const activeLabel = selected === "auto" ? (data?.auto?.label ? `Auto · ${data.auto.label}` : "Auto") : current?.label ?? selected;
  const usable = useMemo(() => flat.filter((m) => USABLE.has(m.state)), [flat]);

  return { data, groups: data?.groups ?? [], auto: data?.auto ?? null, flat, usable, selected, current, activeLabel, loading, error, refresh, select };
}
export type ModelsState = ReturnType<typeof useModels>;
