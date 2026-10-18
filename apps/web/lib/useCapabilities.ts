"use client";
import { useCallback, useEffect, useState } from "react";
import { getCapabilities } from "./api";
import type { Capabilities } from "./api";

export function useCapabilities() {
  const [caps, setCaps] = useState<Capabilities | null>(null);
  const refresh = useCallback(() => { getCapabilities().then(setCaps).catch(() => {}); }, []);
  useEffect(() => { refresh(); }, [refresh]);
  return { caps, refresh };
}
